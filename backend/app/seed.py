from pathlib import Path

from backend.app.storage.repository import now

USERS = [
    ("admin", "平台管理员", "Admin@123456", "team-platform", ["PlatformAdmin", "Reviewer"], "owner"),
    ("zhangsan", "张三", "ZhangSan@123456", "team-dev-a", ["Member", "SkillAuthor"], "member"),
    ("lisi", "李四", "LiSi@123456", "team-dev-b", ["Member", "SkillAuthor"], "owner"),
    ("wangwu", "王五", "WangWu@123456", "team-ops", ["Member", "SkillAuthor"], "member"),
    ("zhaoliu", "赵六", "ZhaoLiu@123456", "team-ai", ["Member", "SkillAuthor"], "member"),
]
TEAMS = [
    ("team-platform", "平台管理", "admin"),
    ("team-dev-a", "研发一组", "zhangsan"),
    ("team-dev-b", "研发二组", "lisi"),
    ("team-ops", "运维组", "wangwu"),
    ("team-ai", "AI 应用组", "zhaoliu"),
]
CATEGORIES = [
    ("ai-coding", "AI Coding"),
    ("testing", "Testing / 测试"),
    ("devops", "DevOps / 运维"),
    ("data", "Data / 数据"),
    ("aigc", "AIGC / 内容创作"),
    ("api-mcp", "API & MCP"),
    ("office", "Office / 知识与办公"),
]
SKILLS = [
    (
        "java-code-review",
        "Java 代码审查清单",
        "ai-coding",
        "zhangsan",
        "team-dev-a",
        "team",
        ["java", "review"],
        "Review Java changes for readability, null safety, logging and exception handling.",
        [
            "理解改动目标和涉及的 Java 类。",
            "检查异常处理、日志、空指针、资源关闭和可读性。",
            "输出问题位置、影响和修改建议。",
        ],
    ),
    (
        "python-style-guide",
        "Python 代码风格提示",
        "ai-coding",
        "lisi",
        "team-dev-b",
        "team",
        ["python", "coding"],
        "Review Python code for readable names, typing and maintainable functions.",
        ["理解模块职责。", "检查命名、类型标注和异常处理。", "提出保持现有行为的改进建议。"],
    ),
    (
        "ack-pod-triage",
        "ACK Pod 故障初排",
        "devops",
        "wangwu",
        "team-ops",
        "team",
        ["kubernetes", "triage"],
        "Triage Kubernetes Pod failures using read-only observations.",
        [
            "收集命名空间、Pod 状态和事件。",
            "阅读日志并区分调度、镜像和应用错误。",
            "先提供证据，不直接修改生产配置。",
        ],
    ),
    (
        "video-summary-outline",
        "视频理解摘要大纲",
        "aigc",
        "zhaoliu",
        "team-ai",
        "team",
        ["video", "summary"],
        "Organize supplied video notes into a concise summary outline.",
        ["依据提供的字幕或笔记整理主题。", "区分事实、观点和不确定信息。", "输出摘要、时间线和待确认事项。"],
    ),
    (
        "unit-test-outline",
        "单元测试用例纲要",
        "testing",
        "admin",
        "team-platform",
        "enterprise",
        ["testing", "quality"],
        "Draft unit test cases for normal paths, boundaries and failures.",
        ["识别输入输出与外部依赖。", "覆盖正常、边界、异常路径。", "优先验证可观察行为。"],
    ),
    (
        "git-commit-guide",
        "Git Commit 说明规范",
        "ai-coding",
        "admin",
        "team-platform",
        "enterprise",
        ["git", "workflow"],
        "Write clear Git commit messages describing the problem and resulting behavior.",
        ["阅读差异并归纳改动目的。", "使用简短标题说明结果。", "补充验证方式；未经用户要求不提交代码。"],
    ),
    (
        "mcp-tool-checklist",
        "MCP 工具设计检查清单",
        "api-mcp",
        "admin",
        "team-platform",
        "enterprise",
        ["mcp", "api"],
        "Review MCP tool inputs, authorization, errors and side effects.",
        ["明确工具输入、输出和操作边界。", "校验身份、权限和错误语义。", "区分读取与写入，并保护凭据。"],
    ),
    (
        "data-cleaning-notes",
        "CSV 数据清理基础流程",
        "data",
        "admin",
        "team-platform",
        "enterprise",
        ["csv", "data"],
        "Plan CSV cleanup while preserving source data and reporting transformations.",
        ["先检查编码、列名和缺失值。", "明确去重和类型转换规则。", "保存原始数据，报告处理数量与异常。"],
    ),
]


def seed(hub):
    from backend.app.auth.identity import PASSWORDS

    with hub.repo.transaction() as tx:
        for username, label, password, team, roles, role in USERS:
            user_id = "user-" + username
            if user_id not in tx["users"]:
                tx["users"][user_id] = {
                    "user_id": user_id,
                    "username": username,
                    "display_name": label,
                    "password_hash": PASSWORDS.hash(password),
                    "disabled": False,
                    "roles": roles,
                    "auth_epoch": 0,
                    "created_at": now(),
                    "updated_at": now(),
                    "revision": 1,
                }
                key = f"{team}:{user_id}"
                tx["memberships"][key] = {
                    "membership_id": key,
                    "user_id": user_id,
                    "team_id": team,
                    "role": role,
                    "status": "active",
                    "created_at": now(),
                    "updated_at": now(),
                }
        for team_id, name, owner in TEAMS:
            tx["teams"].setdefault(
                team_id,
                {
                    "team_id": team_id,
                    "name": name,
                    "owner_user_id": "user-" + owner,
                    "description": "本机演示团队",
                    "archived": False,
                    "internal": team_id == "team-platform",
                    "created_at": now(),
                    "updated_at": now(),
                    "revision": 1,
                },
            )
        for category_id, name in CATEGORIES:
            tx["categories"].setdefault(category_id, {"category_id": category_id, "name": name})
        for name, label, category, owner, team, visibility, tags, description, instructions in SKILLS:
            if name in tx["skills"]:
                continue
            content = "---\nname: " + name + "\ndescription: " + description + "\n---\n\n# " + label + "\n\n"
            content += "\n".join(f"{i + 1}. {line}" for i, line in enumerate(instructions))
            content += "\n\n只使用已授权的数据和工具；不要自动执行生产变更。\n"
            source = Path(__file__).resolve().parents[2] / "seed" / "skills" / name / "SKILL.md"
            if source.exists():
                content = source.read_text()
            stored = hub.packages.save({"SKILL.md": content.encode()}, name, "1.0.0")
            metadata = {
                "display_name": label,
                "description": description,
                "category_id": category,
                "tags": tags,
                "visibility": visibility,
                "acl": [],
            }
            tx["skills"][name] = {
                "skill_id": name,
                "name": name,
                "owner_user_id": "user-" + owner,
                "owner_team_id": team,
                "current_version": "1.0.0",
                "created_at": now(),
                "updated_at": now(),
                "published_at": now(),
                "revision": 1,
                "seeded": True,
                **metadata,
            }
            tx["versions"][name + "@1.0.0"] = {
                **stored,
                "skill_id": name,
                "version": "1.0.0",
                "status": "published",
                "proposed_metadata": metadata,
                "submitted_by": "user-" + owner,
                "created_at": now(),
                "updated_at": now(),
                "published_at": now(),
                "revision": 1,
                "review_id": None,
                "seeded": True,
            }
        for collection_id, name, team, skills in [
            ("col-dev-a", "研发一组常用技能", "team-dev-a", ["java-code-review", "git-commit-guide"]),
            ("col-dev-b", "研发二组提效工具", "team-dev-b", ["python-style-guide", "unit-test-outline"]),
            ("col-ops", "运维排障集", "team-ops", ["ack-pod-triage"]),
        ]:
            tx["collections"].setdefault(
                collection_id,
                {
                    "collection_id": collection_id,
                    "name": name,
                    "owner_team_id": team,
                    "skill_ids": skills,
                    "acl": [],
                    "archived": False,
                    "created_at": now(),
                    "updated_at": now(),
                    "revision": 1,
                },
            )
        # Only add initial favorites for a brand-new seed; later startup must preserve removals.
        if not (hub.settings.data_dir / ".seeded").exists():
            for username, names in [
                ("zhangsan", ["java-code-review", "mcp-tool-checklist"]),
                ("lisi", ["python-style-guide", "git-commit-guide"]),
            ]:
                for name in names:
                    key = f"user-{username}:{name}"
                    tx["favorites"].setdefault(
                        key, {"user_id": "user-" + username, "skill_id": name, "created_at": now()}
                    )
            tx.audit("system", "seed_demo", result="initialized")
    from backend.app.storage.repository import atomic_write

    atomic_write(hub.settings.data_dir / ".seeded", b"1\n")
