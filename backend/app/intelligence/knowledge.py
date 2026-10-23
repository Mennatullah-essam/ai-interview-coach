"""Curated knowledge used by the intelligence engine: skills, aliases, roles.

All of it is version-controlled data in app/data/, loaded once and cached.
Nothing here calls a model or the network.
"""

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.config import APP_DIR, get_settings
from app.services.cv_parsing import load_skills

DATA_DIR = APP_DIR / "data"


@dataclass(frozen=True)
class RoleRequirements:
    name: str
    description: str
    required_skills: tuple[str, ...]
    preferred_skills: tuple[str, ...]
    competencies: tuple[str, ...]


@dataclass
class SkillCatalog:
    names: tuple[str, ...]
    category_of: dict[str, str]
    aliases: dict[str, str]
    soft_skill_patterns: dict[str, list[re.Pattern]] = field(default_factory=dict)

    def normalize(self, raw: str) -> str | None:
        """Map a free-text skill to its canonical name, or None if unknown."""
        cleaned = re.sub(r"\s+", " ", raw.strip())
        if not cleaned:
            return None
        lowered = cleaned.lower()
        for name in self.names:
            if name.lower() == lowered:
                return name
        for alias, target in self.aliases.items():
            if alias.lower() == lowered:
                return target
        return None


@lru_cache
def skill_catalog() -> SkillCatalog:
    data = json.loads((DATA_DIR / "skill_catalog.json").read_text(encoding="utf-8"))
    names = load_skills(get_settings().skills_list_path)
    category_of = {skill: category for category, skills in data["categories"].items() for skill in skills}
    soft = {
        name: [re.compile(p, re.IGNORECASE) for p in patterns]
        for name, patterns in data["soft_skills"].items()
    }
    return SkillCatalog(names=names, category_of=category_of, aliases=dict(data["aliases"]), soft_skill_patterns=soft)


@lru_cache
def _alias_patterns() -> tuple[tuple[re.Pattern, str], ...]:
    patterns = []
    for alias, target in skill_catalog().aliases.items():
        flags = 0 if len(alias) <= 2 else re.IGNORECASE
        patterns.append((re.compile(rf"(?<![A-Za-z0-9+#.]){re.escape(alias)}(?![A-Za-z0-9+#])", flags), target))
    return tuple(patterns)


def find_alias_skills(text: str) -> list[str]:
    """Canonical skills mentioned only through an alias (e.g. 'sklearn', 'k8s')."""
    found = []
    for pattern, target in _alias_patterns():
        if target not in found and pattern.search(text):
            found.append(target)
    return found


def normalize_skill_list(raw: list[str]) -> list[str]:
    """Canonicalise known skills, keep unknown ones (trimmed, original case), drop duplicates."""
    catalog = skill_catalog()
    seen: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        canonical = catalog.normalize(item) or re.sub(r"\s+", " ", item.strip())[:60]
        seen.setdefault(canonical.lower(), canonical)
    return list(seen.values())


@lru_cache
def roles() -> dict[str, RoleRequirements]:
    data = json.loads((DATA_DIR / "roles.json").read_text(encoding="utf-8"))
    return {
        name: RoleRequirements(
            name=name,
            description=spec["description"],
            required_skills=tuple(spec["required_skills"]),
            preferred_skills=tuple(spec["preferred_skills"]),
            competencies=tuple(spec["competencies"]),
        )
        for name, spec in data["roles"].items()
    }


def role_requirements(role_names: set[str]) -> RoleRequirements | None:
    """Merge the requirement profiles of one or more matched preset roles."""
    matched = [roles()[r] for r in sorted(role_names) if r in roles()]
    if not matched:
        return None
    if len(matched) == 1:
        return matched[0]
    required = list(dict.fromkeys(s for r in matched for s in r.required_skills))
    preferred = [s for s in dict.fromkeys(s for r in matched for s in r.preferred_skills) if s not in required]
    return RoleRequirements(
        name=" / ".join(r.name for r in matched),
        description=" ".join(r.description for r in matched),
        required_skills=tuple(required),
        preferred_skills=tuple(preferred),
        competencies=tuple(dict.fromkeys(c for r in matched for c in r.competencies)),
    )


def data_path(name: str) -> Path:
    return DATA_DIR / name
