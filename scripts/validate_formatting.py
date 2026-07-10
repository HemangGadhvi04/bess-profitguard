from __future__ import annotations

from pathlib import Path


CHECKED_SUFFIXES = {".py", ".md", ".yml", ".yaml"}
CHECKED_NAMES = {"Makefile"}
EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "runs"}


def iter_checked_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix in CHECKED_SUFFIXES or path.name in CHECKED_NAMES:
            files.append(path)
    return sorted(files)


def validate_file(path: Path) -> list[str]:
    issues: list[str] = []
    contents = path.read_bytes()
    if not contents:
        return issues
    if b"\r\n" in contents:
        issues.append("uses CRLF line endings")
    if not contents.endswith(b"\n"):
        issues.append("does not end with a newline")
    if b"\x00" in contents:
        issues.append("contains NUL bytes")
    return issues


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for path in iter_checked_files(root):
        for issue in validate_file(path):
            failures.append(f"{path.relative_to(root)}: {issue}")

    if failures:
        print("Formatting validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Formatting validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
