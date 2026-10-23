"""Load, check and seed the curated question bank (API spec 8.3, OD-14).

The bank lives in app/data/question_bank.json (version-controlled) and is
copied into the question_bank table by scripts/seed_question_bank.py.
Seeding is idempotent: entries are matched by their text, updated in place,
and entries removed from the file are deactivated (never deleted, because
past interviews may reference them).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuestionBankItem
from app.models.enums import Difficulty, QuestionKind, QuestionType

PRESET_ROLES = (
    "AI Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
    "Software Engineer",
    "Backend Developer",
    "Frontend Developer",
    "Data Analyst",
)
MAX_QUESTION_COUNT = 15
MAX_REFERENCE_WORDS = 150  # the embedding model truncates long inputs (spec 8.3)


@dataclass
class BankEntry:
    kind: QuestionKind
    text: str
    question_type: QuestionType
    difficulty: Difficulty | None
    role_tags: list[str]
    skill_tags: list[str]
    reference_answer: str
    key_points: list[str]
    misconceptions: list[dict] = field(default_factory=list)


def load_bank_file(path: Path) -> tuple[list[BankEntry], str | None]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = []
    for item in raw["questions"]:
        entries.append(
            BankEntry(
                kind=QuestionKind(item.get("kind", "generic")),
                text=item["text"].strip(),
                question_type=QuestionType(item["type"]),
                difficulty=Difficulty(item["difficulty"]) if item.get("difficulty") else None,
                role_tags=list(item.get("role_tags") or ["general"]),
                skill_tags=list(item.get("skill_tags") or []),
                reference_answer=item["reference_answer"].strip(),
                key_points=list(item["key_points"]),
                misconceptions=list(item.get("misconceptions") or []),
            )
        )
    return entries, raw.get("source_note")


def check_bank(entries: list[BankEntry]) -> list[str]:
    """Return a list of problems; empty means the bank is usable."""
    problems = []
    texts = [e.text.lower() for e in entries]
    if len(texts) != len(set(texts)):
        problems.append("duplicate question texts")
    for e in entries:
        words = len(e.reference_answer.split())
        if words > MAX_REFERENCE_WORDS:
            problems.append(f"reference answer too long ({words} words): {e.text[:60]}")
        if not 3 <= len(e.key_points) <= 6:
            problems.append(f"needs 3-6 key points: {e.text[:60]}")
        unknown = [r for r in e.role_tags if r != "general" and r not in PRESET_ROLES]
        if unknown:
            problems.append(f"unknown role tags {unknown}: {e.text[:60]}")
        if e.kind is QuestionKind.SKILL_TEMPLATE and "{skill}" not in e.text:
            problems.append(f"skill template without {{skill}}: {e.text[:60]}")
        if e.kind is QuestionKind.PROJECT_TEMPLATE and "{project}" not in e.text:
            problems.append(f"project template without {{project}}: {e.text[:60]}")
        for item in e.misconceptions:
            try:
                re.compile(item["pattern"])
                assert item.get("explanation")
            except (re.error, KeyError, AssertionError):
                problems.append(f"invalid misconception entry: {e.text[:60]}")

    generic = [e for e in entries if e.kind is QuestionKind.GENERIC]
    for qtype in QuestionType:
        general_pool = [e for e in generic if e.question_type is qtype and "general" in e.role_tags]
        if len(general_pool) < MAX_QUESTION_COUNT:
            problems.append(
                f"only {len(general_pool)} general {qtype.value} questions; custom roles need {MAX_QUESTION_COUNT}"
            )
        for role in PRESET_ROLES:
            pool = [e for e in generic if e.question_type is qtype and ("general" in e.role_tags or role in e.role_tags)]
            if len(pool) < MAX_QUESTION_COUNT:
                problems.append(f"only {len(pool)} {qtype.value} questions for {role}")
    return problems


def seed_bank(db: Session, entries: list[BankEntry], source_note: str | None) -> dict[str, int]:
    existing = {item.text: item for item in db.scalars(select(QuestionBankItem))}
    stats = {"created": 0, "updated": 0, "deactivated": 0}
    seen = set()
    for e in entries:
        seen.add(e.text)
        item = existing.get(e.text)
        if item is None:
            item = QuestionBankItem(text=e.text)
            db.add(item)
            stats["created"] += 1
        else:
            stats["updated"] += 1
        item.kind = e.kind
        item.question_type = e.question_type
        item.difficulty = e.difficulty
        item.role_tags = e.role_tags
        item.skill_tags = e.skill_tags
        item.ideal_answer = e.reference_answer
        item.key_points = e.key_points
        item.misconceptions = e.misconceptions
        item.source_note = (source_note or "")[:255] or None
        item.is_active = True
    for text, item in existing.items():
        if text not in seen and item.is_active:
            item.is_active = False
            stats["deactivated"] += 1
    db.commit()
    return stats
