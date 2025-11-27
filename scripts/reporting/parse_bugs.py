"""Extract active issues from the Known Bugs Ledger for reporting."""

import json
from pathlib import Path
from typing import Dict, List

_DESIRED_COLUMNS = ("ID", "Title", "Severity", "Status", "Owner")
_EXCLUDED_STATUSES = {"resolved", "archived"}


def parse_known_bugs(file_path: Path) -> List[Dict[str, str]]:
    """Return parsed rows containing only active bugs with requested columns."""

    headers: List[str] = []
    output: List[Dict[str, str]] = []
    table_started = False

    with file_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped.startswith("|"):
                if table_started:
                    break
                continue

            if stripped.startswith("| ---"):
                table_started = True
                continue

            cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
            if not cells:
                continue

            if not headers:
                header_set = {cell for cell in cells if cell}
                if not header_set.issuperset(_DESIRED_COLUMNS):
                    continue
                headers = cells
                table_started = True
                continue

            table_started = True

            row = {headers[idx]: cells[idx] if idx < len(cells) else "" for idx in range(len(headers))}
            filtered = {col: row.get(col, "") for col in _DESIRED_COLUMNS}
            status = filtered.get("Status", "").strip().lower()
            if status in _EXCLUDED_STATUSES:
                continue

            output.append(filtered)

    return output


def main() -> None:
    script_path = Path(__file__).resolve()
    parents = script_path.parents
    repo_root = parents[2] if len(parents) > 2 else script_path.parent
    source_file = repo_root / "docs" / "status" / "KnownBugs.md"
    bugs = parse_known_bugs(source_file)
    print(json.dumps(bugs, indent=2))


if __name__ == "__main__":
    main()
