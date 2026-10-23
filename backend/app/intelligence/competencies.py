"""Shared competency model (Milestone 5).

One vocabulary for the whole intelligence layer:

  retrieval   selects a question to assess competencies   (question focus skills)
  evaluator   scores the answer against that question's rubric
  agent       decides whether to probe a competency further
  coaching    aggregates the evidence per competency across interviews
  retrieval   uses that evidence to choose the next interview's questions

A competency id is "skill:<canonical skill>" or "behavior:<competency>".

Evidence is kept apart by origin and never merged into one "truth":
  profile      extracted from the CV, inferred by a rule, or added by the user
  interview    demonstrated / developing / weak / needs_evidence, from scored answers
  unassessed   no interview evidence yet
A weak answer never removes or overrides a skill the candidate confirmed in their profile.
"""

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.intelligence.knowledge import DATA_DIR, skill_catalog

DEMONSTRATED_FROM = 75
WEAK_BELOW = 55
GAP_MIN_EVIDENCE = 2


@dataclass(frozen=True)
class Competency:
    id: str
    name: str
    kind: str  # skill | behavior
    description: str
    related: tuple[str, ...] = ()


@dataclass
class CompetencyModel:
    by_id: dict[str, Competency]
    by_lower_name: dict[str, Competency]

    def get(self, name_or_id: str) -> Competency | None:
        if name_or_id in self.by_id:
            return self.by_id[name_or_id]
        return self.by_lower_name.get(name_or_id.strip().lower())

    def id_for(self, name: str, kind: str = "skill") -> str:
        """Stable id for a skill or behavioral competency; unknown names keep their own name."""
        found = self.get(name)
        if found is not None:
            return found.id
        canonical = skill_catalog().normalize(name) or name.strip()
        found = self.get(canonical)
        return found.id if found is not None else f"{kind}:{canonical}"

    def description(self, name: str) -> str:
        found = self.get(name)
        return found.description if found is not None else ""

    def related(self, name: str) -> list[str]:
        found = self.get(name)
        return list(found.related) if found is not None else []


@lru_cache
def competency_model() -> CompetencyModel:
    data = json.loads((DATA_DIR / "competencies.json").read_text(encoding="utf-8"))
    items: list[Competency] = []
    for name, info in data["skills"].items():
        items.append(Competency(id=f"skill:{name}", name=name, kind="skill", description=info["description"],
                                related=tuple(info.get("related", []))))
    for name, info in data["behaviors"].items():
        items.append(Competency(id=f"behavior:{name}", name=name, kind="behavior", description=info["description"]))
    return CompetencyModel(by_id={c.id: c for c in items}, by_lower_name={c.name.lower(): c for c in items})


def ids_for(names: list[str], question_type: str = "technical") -> list[str]:
    kind = "behavior" if question_type == "behavioral" else "skill"
    model = competency_model()
    return list(dict.fromkeys(model.id_for(n, kind) for n in names if n))


def name_of(competency_id: str) -> str:
    return competency_id.split(":", 1)[-1]


# --- evidence ledger -------------------------------------------------------------------------


@dataclass
class CompetencyEvidence:
    id: str
    name: str
    profile_source: str | None = None  # extracted | inferred | user | None
    scores: list[int] = field(default_factory=list)  # interview evidence, oldest first
    interviews: set[str] = field(default_factory=set)
    last_scores: list[int] = field(default_factory=list)  # from the most recent interview that assessed it

    @property
    def interview_status(self) -> str:
        """demonstrated | developing | weak | needs_evidence | unassessed (interview evidence only)."""
        if not self.scores:
            return "unassessed"
        average = sum(self.scores) / len(self.scores)
        if average >= DEMONSTRATED_FROM:
            return "demonstrated"
        if average < WEAK_BELOW:
            weak = sum(1 for s in self.scores if s < WEAK_BELOW)
            return "weak" if weak >= GAP_MIN_EVIDENCE else "needs_evidence"
        return "developing"

    @property
    def average(self) -> int | None:
        return round(sum(self.scores) / len(self.scores)) if self.scores else None

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "profile_source": self.profile_source,
                "interview_status": self.interview_status, "average": self.average,
                "answers": len(self.scores), "interviews": len(self.interviews)}


@dataclass
class CompetencyLedger:
    items: dict[str, CompetencyEvidence] = field(default_factory=dict)

    def entry(self, competency_id: str) -> CompetencyEvidence:
        if competency_id not in self.items:
            self.items[competency_id] = CompetencyEvidence(id=competency_id, name=name_of(competency_id))
        return self.items[competency_id]

    def status(self, name: str) -> str:
        found = self.items.get(competency_model().id_for(name))
        return found.interview_status if found else "unassessed"

    def needs_assessment(self, name: str) -> bool:
        """True when interview evidence is missing, thin or weak (worth asking about again)."""
        return self.status(name) in ("unassessed", "needs_evidence", "weak")


def build_ledger(profile=None, answers=()) -> CompetencyLedger:
    """Combine profile provenance with scored interview answers.

    `answers` are objects with `interview_id`, `question_type`, `focus_skills`,
    `category` and `knowledge_score` / `overall` (see improvement.AnswerEvidence).
    """
    ledger = CompetencyLedger()
    model = competency_model()
    if profile is not None:
        for skill in profile.technical_skills:
            ledger.entry(model.id_for(skill.name)).profile_source = skill.source
        for skill in profile.soft_skills:
            ledger.entry(model.id_for(skill.name, "behavior")).profile_source = skill.source
    last_by_id: dict[str, tuple[str, list[int]]] = {}
    for answer in answers:
        if answer.category == "project" or not answer.focus_skills:
            continue
        behavioral = answer.question_type == "behavioral"
        score = answer.overall if behavioral else answer.knowledge_score
        for cid in ids_for(answer.focus_skills, answer.question_type):
            item = ledger.entry(cid)
            item.scores.append(score)
            item.interviews.add(answer.interview_id)
            prev = last_by_id.get(cid)
            if prev is None or prev[0] != answer.interview_id:
                last_by_id[cid] = (answer.interview_id, [score])
            else:
                prev[1].append(score)
    for cid, (_, scores) in last_by_id.items():
        ledger.items[cid].last_scores = scores
    return ledger


_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")
