import hashlib
from io import BytesIO
import re
import stat
import unicodedata
from pathlib import PurePosixPath
import zipfile

import yaml

from backend.app.errors import require, HubError
from backend.app.storage.repository import atomic_write

NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PRE_ID = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    + rf"(?:-({_PRE_ID}(?:\.{_PRE_ID})*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|"
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bLTAI[A-Za-z0-9]{16,}\b|"
    r"\b(?:sk-proj-|sk-ant-)[A-Za-z0-9_-]{20,}|"
    r"(?im:^\s*(?:api[_-]?key|access[_-]?key|secret[_-]?key|password|token)\s*[:=]\s*['\"]?[^\s'\"]{8,})"
)


def digest(content: bytes):
    return hashlib.sha256(content).hexdigest()


def safe_path(path: str):
    parts = PurePosixPath(path).parts
    require(
        bool(path)
        and not path.startswith("/")
        and "\\" not in path
        and "\x00" not in path
        and ":" not in path
        and all(p not in {"..", "."} for p in path.split("/"))
        and not any(ord(c) < 32 for c in path),
        "UPLOAD_INVALID",
        "文件相对路径不安全",
        400,
    )
    require(len(path) <= 240 and len(parts) <= 12, "UPLOAD_INVALID", "文件路径过长", 400)
    return "/".join(parts)


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        require(
            isinstance(key, str) and key not in result, "UPLOAD_INVALID", "frontmatter 字段重复或非法", 400
        )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def parse_skill(content: bytes):
    try:
        text = content.decode("utf-8-sig")
        require(
            text.startswith("---\n") or text.startswith("---\r\n"),
            "UPLOAD_INVALID",
            "缺少 YAML frontmatter",
            400,
        )
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        require(
            match is not None and len(match[1]) <= 16384, "UPLOAD_INVALID", "frontmatter 不完整或过大", 400
        )
        require(
            not any(
                isinstance(t, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken, yaml.tokens.TagToken))
                for t in yaml.scan(match[1])
            ),
            "UPLOAD_INVALID",
            "frontmatter 不允许别名、锚点或自定义标签",
            400,
        )
        data = yaml.load(match[1], Loader=UniqueLoader)
        require(isinstance(data, dict), "UPLOAD_INVALID", "frontmatter 必须是对象", 400)
        name, description = data.get("name"), data.get("description")
        require(
            isinstance(name, str) and len(name) <= 64 and NAME.fullmatch(name) is not None,
            "UPLOAD_INVALID",
            "name 须为最长 64 字符的小写字母、数字和单连字符",
            400,
        )
        require(
            isinstance(description, str) and 0 < len(description.strip()) <= 1024,
            "UPLOAD_INVALID",
            "description 必填，最长 1024 字符",
            400,
        )
        return data
    except (UnicodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        raise HubError("UPLOAD_INVALID", "SKILL.md 必须包含有效的 UTF-8 和 YAML", 400) from exc


class Packages:
    def __init__(self, settings):
        self.settings = settings

    def validate(self, files):
        cfg = self.settings
        require(
            0 < len(files) <= cfg.max_files and sum(map(len, files.values())) <= cfg.max_expanded,
            "UPLOAD_INVALID",
            "文件数或解压大小超出限制",
            400,
        )
        require(
            "SKILL.md" in files and sum(p.endswith("SKILL.md") for p in files) == 1,
            "UPLOAD_INVALID",
            "包内须且仅有一个根目录 SKILL.md",
            400,
        )
        warnings = []
        folded = set()
        for path, content in files.items():
            safe_path(path)
            canonical = unicodedata.normalize("NFC", path).casefold()
            require(canonical not in folded, "UPLOAD_INVALID", "包内存在重复或大小写冲突路径", 400)
            folded.add(canonical)
            parts = PurePosixPath(path).parts
            require(
                not any(
                    p in {".git", ".env", ".aws", ".ssh", ".skill-hub-install.json"}
                    or p.startswith(".env.")
                    or p.lower() in {"credentials", "id_rsa", "id_ed25519"}
                    for p in parts
                ),
                "UPLOAD_INVALID",
                "包内包含凭据或非 Skill 文件",
                400,
            )
            text = content.decode("utf-8", errors="replace")
            require(not SECRET.search(text), "UPLOAD_INVALID", "发现高置信度凭据，请移除后重新上传", 400)
            if path.startswith("scripts/"):
                warnings.append({"path": path, "rule": "script_present", "message": "包含脚本；平台不会执行"})
            if re.search(
                r"(?:ignore (?:all |previous )?instructions|忽略.{0,12}(?:系统|指令)|curl.+\|\s*(?:sh|bash)|rm\s+-rf)",
                text,
                re.I,
            ):
                warnings.append({"path": path, "rule": "manual_review", "message": "指令或命令需要人工核对"})
        for path in files:
            require(
                not any(
                    parent in folded
                    for parent in [
                        unicodedata.normalize("NFC", str(p)).casefold()
                        for p in PurePosixPath(path).parents
                        if str(p) != "."
                    ]
                ),
                "UPLOAD_INVALID",
                "文件与目录路径冲突",
                400,
            )
        return parse_skill(files["SKILL.md"]), warnings

    def unpack(self, content):
        require(len(content) <= self.settings.max_zip, "UPLOAD_INVALID", "ZIP 超过大小限制", 400)
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                require(len(entries) <= self.settings.max_files * 2, "UPLOAD_INVALID", "归档条目过多", 400)
                paths, files, total = set(), {}, 0
                for entry in entries:
                    path = safe_path(entry.filename.rstrip("/"))
                    key = unicodedata.normalize("NFC", path).casefold()
                    require(key not in paths, "UPLOAD_INVALID", "ZIP 路径重复", 400)
                    paths.add(key)
                    mode = entry.external_attr >> 16
                    require(
                        stat.S_IFMT(mode) in {0, stat.S_IFDIR, stat.S_IFREG} and not entry.flag_bits & 1,
                        "UPLOAD_INVALID",
                        "ZIP 不允许链接、特殊文件或加密条目",
                        400,
                    )
                    if entry.is_dir():
                        continue
                    total += entry.file_size
                    require(
                        total <= self.settings.max_expanded
                        and len(files) < self.settings.max_files
                        and entry.file_size <= max(1, entry.compress_size) * 150,
                        "UPLOAD_INVALID",
                        "ZIP 文件数量、展开大小或压缩比异常",
                        400,
                    )
                    with archive.open(entry) as stream:
                        body = stream.read(min(self.settings.max_expanded + 1, entry.file_size + 1))
                    require(len(body) == entry.file_size, "UPLOAD_INVALID", "ZIP 条目大小不一致", 400)
                    files[path] = body
                if "SKILL.md" not in files:
                    roots = {p.split("/")[0] for p in files}
                    require(
                        len(roots) == 1, "UPLOAD_INVALID", "ZIP 仅支持根 SKILL.md 或一个 Skill 包装目录", 400
                    )
                    root = next(iter(roots))
                    require(all("/" in p for p in files), "UPLOAD_INVALID", "ZIP 根结构无效", 400)
                    files = {p.split("/", 1)[1]: value for p, value in files.items()}
                    meta, _ = self.validate(files)
                    require(root == meta["name"], "UPLOAD_INVALID", "包装目录须与 Skill name 一致", 400)
                self.validate(files)
                return files
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError, EOFError) as exc:
            raise HubError("UPLOAD_INVALID", "ZIP 损坏或格式不受支持", 400) from exc

    def save(self, files, skill_id, version):
        meta, warnings = self.validate(files)
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, body in sorted(files.items()):
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                archive.writestr(info, body, compress_type=zipfile.ZIP_DEFLATED)
        bundle = output.getvalue()
        require(len(bundle) <= self.settings.max_zip, "UPLOAD_INVALID", "归档超过大小限制", 400)
        sha = digest(bundle)
        bundle_path = f"bundles/{skill_id}/{version}/{sha}.zip"
        expanded_path = f"expanded/{skill_id}/{version}/{sha}"
        atomic_write(self.settings.data_dir / bundle_path, bundle)
        manifest = []
        for path, body in sorted(files.items()):
            atomic_write(self.settings.data_dir / expanded_path / path, body)
            try:
                body.decode("utf-8")
                binary = False
            except UnicodeError:
                binary = True
            manifest.append({"path": path, "size": len(body), "sha256": digest(body), "binary": binary})
        return {
            "bundle_path": bundle_path,
            "expanded_path": expanded_path,
            "sha256": sha,
            "manifest": manifest,
            "risk": "review_required" if warnings else "low",
            "scan": warnings,
            "frontmatter": meta,
        }
