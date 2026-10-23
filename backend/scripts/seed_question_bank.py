"""Check app/data/question_bank.json and copy it into the question_bank table.

Usage (from the backend folder, virtual environment active):
    python scripts/seed_question_bank.py           # check, then seed
    python scripts/seed_question_bank.py --check   # only check the file

Safe to run repeatedly: entries are matched by their text and updated in place;
entries removed from the file are deactivated, never deleted.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.services.question_bank import check_bank, load_bank_file, seed_bank  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only validate the file")
    args = parser.parse_args()

    path = get_settings().question_bank_path
    entries, source_note = load_bank_file(path)
    problems = check_bank(entries)
    if problems:
        print(f"Question bank has {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Question bank OK: {len(entries)} entries in {path.name}")
    if args.check:
        return 0

    with get_session_factory()() as db:
        stats = seed_bank(db, entries, source_note)
    print(f"Seeded: {stats['created']} created, {stats['updated']} updated, {stats['deactivated']} deactivated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
