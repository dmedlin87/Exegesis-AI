from pathlib import Path


def ensure_dirs(paths: list[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def unique_destination(dest_path: Path) -> Path:
    if not dest_path.exists():
        return dest_path
    parent = dest_path.parent
    stem = dest_path.stem
    suffix = dest_path.suffix
    index = 1
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def main() -> None:
    docs_root = Path("docs")
    if not docs_root.exists():
        raise SystemExit("docs/ directory is missing.")

    archive_cleanup = docs_root / "archive" / "cleanup_2025_11"
    target_dirs = [
        docs_root / "specs",
        docs_root / "guides",
        docs_root / "reference",
        docs_root / "planning",
        archive_cleanup,
    ]
    ensure_dirs(target_dirs)

    protected_files = {
        docs_root / "00_DOCUMENTATION_STRATEGY.md",
        docs_root / "README.md",
    }

    report: list[str] = []
    for entry in sorted(docs_root.iterdir()):
        if not entry.is_file():
            continue
        if entry in protected_files:
            continue

        filename_lower = entry.name.lower()
        destination = archive_cleanup
        if filename_lower.endswith((".txt", ".log")):
            destination = archive_cleanup
        elif "api" in filename_lower or "schema" in filename_lower:
            destination = docs_root / "reference"
        elif "guide" in filename_lower or "how" in filename_lower:
            destination = docs_root / "guides"
        elif "plan" in filename_lower or "roadmap" in filename_lower:
            destination = docs_root / "planning"
        elif entry.suffix == ".md":
            destination = archive_cleanup
        else:
            destination = archive_cleanup

        dest_file = unique_destination(destination / entry.name)
        old_path = entry
        entry.rename(dest_file)
        report.append(f"Moved {old_path} -> {dest_file}")

    if report:
        print("Documents reorganized:")
        for line in report:
            print(f"- {line}")
    else:
        print("No loose docs/ files required moving.")


if __name__ == "__main__":
    main()
