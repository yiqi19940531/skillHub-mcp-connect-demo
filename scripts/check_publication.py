"""Check tracked publication files without printing candidate credential values."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "GitHub credential": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b",
    "API credential": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{28,}\b",
    "cloud access key": r"\bAKIA[A-Z0-9]{16}\b",
    "JWT credential": r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b",
    "private key material": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\n]{60,}",
    "personal home path": r"/Users/(?!example(?:/|\b)|demo(?:/|\b)|USER(?:/|\b))[A-Za-z0-9_.-]+/",
    "non-example email": r"\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|org)|users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
}
FORBIDDEN = (
    "data/",
    ".venv/",
    "test-results/",
    "frontend/node_modules/",
    "frontend/dist/",
    ".agents/",
    ".qoder/",
)


def main():
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    findings = []
    for relative in filter(None, files):
        if relative.startswith(FORBIDDEN) or relative == ".env" or relative.endswith((".pem", ".key")):
            findings.append((relative, "runtime or credential file", 0))
            continue
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        # This scanner defines signatures, but does not contain real credentials.
        if relative == "scripts/check_publication.py":
            continue
        for label, pattern in PATTERNS.items():
            for match in re.finditer(pattern, text):
                findings.append((relative, label, text[: match.start()].count("\n") + 1))
    if findings:
        for filename, label, line in findings:
            print(f"{filename}:{line}: {label}")
        raise SystemExit("Publication check failed; values have not been printed.")
    print(
        f"Publication check passed: {len(list(filter(None, files)))} tracked files; no matching credentials or private home paths."
    )


if __name__ == "__main__":
    main()
