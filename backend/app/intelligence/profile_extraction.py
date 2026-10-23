"""CV text -> structured candidate profile (Milestone 4, feature 1).

Deterministic and explainable. Each item is either
  * extracted: literally present in the CV (evidence = the CV line), or
  * inferred: derived by a stated rule (evidence = the reasoning).
Nothing is invented: if the CV does not mention something it stays empty,
and a warning tells the candidate what could not be found.
"""

import re
from datetime import date

from app.core.config import get_settings
from app.intelligence.knowledge import find_alias_skills, role_requirements, roles, skill_catalog
from app.schemas.profile import (
    ExperienceEntry,
    InferredValue,
    LevelValue,
    ProfileData,
    ProjectEntry,
    SkillItem,
    TextItem,
    YearsValue,
)
from app.services.cv_parsing import find_skills, load_skills
from app.services.question_selection import match_roles

EXTRACTOR_VERSION = "profile-rules-v1"

_BULLET = "•-*·▪●◦‣–"
_HEADINGS = {
    "summary": r"(professional )?(summary|profile|about me|objective|career objective)",
    "experience": r"(work |professional )?(experience|employment( history)?|work history|internships?)",
    "education": r"(education|academic background|qualifications)",
    "projects": r"(projects?|personal projects|selected projects|academic projects)",
    "skills": r"(technical )?(skills|technologies|tech stack|tools)",
    "achievements": r"(achievements|awards|honou?rs|accomplishments)",
    "certifications": r"(certifications?|courses|licenses)",
    "interests": r"(interests|career interests|hobbies)",
    "other": r"(languages|references|contact|volunteering|activities)",
}
_HEADING_RE = {name: re.compile(rf"^{pattern}\s*:?$", re.IGNORECASE) for name, pattern in _HEADINGS.items()}
_ACTION_VERBS = (
    "built|developed|designed|implemented|created|led|managed|improved|reduced|increased|optimi[sz]ed|"
    "deployed|automated|analy[sz]ed|wrote|trained|maintained|migrated|launched|delivered|collaborated|"
    "worked|mentored|tested|researched|achieved|won|awarded|organi[sz]ed|presented|integrated|cleaned|"
    "graded|taught|supported|assisted|handled|prepared|conducted|coordinated|contributed|helped|used"
)
_RESPONSIBILITY_RE = re.compile(rf"^({_ACTION_VERBS})\b", re.IGNORECASE)
# An achievement needs a result: an improvement with a number, a percentage, or an award.
_ACHIEVEMENT_RE = re.compile(
    r"(\b(improv|reduc|increas|achiev|sav|grew|grow|cut|boost|rais|doubl|exceed)\w*\b.*\d)|"
    r"(\d+(\.\d+)?\s?(%|percent)|\b\d+(\.\d+)?x\b)|\b(award|winner|won|ranked|first place|"
    r"scholarship|published|certified|dean'?s list|honou?rs)\b",
    re.IGNORECASE,
)
_MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_YEAR_RANGE = re.compile(
    rf"(?:{_MONTHS}\s*)?((?:19|20)\d\d)\s*(?:-|–|—|to|until)\s*(?:{_MONTHS}\s*)?((?:19|20)\d\d|present|current|now|today)",
    re.IGNORECASE,
)
_SINGLE_YEAR = re.compile(r"\(((?:19|20)\d\d)\)")
_YEARS_STATED = re.compile(r"(\d{1,2}(?:\.\d)?)\+?\s*(?:years|yrs)\s+(?:of\s+)?(?:professional\s+|industry\s+|work\s+)?experience", re.IGNORECASE)
_STUDENT_RE = re.compile(r"\b(student|undergraduate|expected (?:graduation )?(?:19|20)\d\d|graduating|final[- ]year|currently studying)\b", re.IGNORECASE)
_SENIOR_TITLE_RE = re.compile(r"\b(senior|lead|principal|staff|head of)\b", re.IGNORECASE)


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().strip(_BULLET).strip())


def _is_bullet(raw: str) -> bool:
    return raw.lstrip()[:1] in _BULLET


def _section_of(line: str) -> str | None:
    if len(line) > 40:
        return None
    return next((name for name, rx in _HEADING_RE.items() if rx.match(line)), None)


def split_sections(text: str) -> dict[str, list[tuple[str, bool]]]:
    """Return {section: [(clean line, was_bullet)]}; text before any heading is 'header'."""
    sections: dict[str, list[tuple[str, bool]]] = {"header": []}
    current = "header"
    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            continue
        heading = _section_of(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append((line, _is_bullet(raw)))
    return sections


def _first_line_with(text_lines: list[str], needle_rx: re.Pattern) -> str | None:
    return next((line for line in text_lines if needle_rx.search(line)), None)


def _skill_pattern(skill: str) -> re.Pattern:
    flags = 0 if len(skill) <= 2 else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9+#.]){re.escape(skill)}(?![A-Za-z0-9+#])", flags)


# --- skills ---------------------------------------------------------------------------------


def extract_technical_skills(text: str, lines: list[str]) -> list[SkillItem]:
    catalog = skill_catalog()
    vocabulary = load_skills(get_settings().skills_list_path)
    names = list(dict.fromkeys([*find_skills(text, vocabulary, limit=80), *find_alias_skills(text)]))
    items = []
    for name in names[:80]:
        evidence = _first_line_with(lines, _skill_pattern(name))
        if evidence is None:  # matched through an alias
            for alias, target in catalog.aliases.items():
                if target == name:
                    evidence = _first_line_with(lines, _skill_pattern(alias))
                    if evidence:
                        break
        items.append(SkillItem(name=name, category=catalog.category_of.get(name), source="extracted",
                               evidence=(evidence or "")[:200] or None))
    return items


def extract_soft_skills(text: str, lines: list[str]) -> list[SkillItem]:
    items = []
    for name, patterns in skill_catalog().soft_skill_patterns.items():
        explicit = _first_line_with(lines, re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE))
        if explicit:
            items.append(SkillItem(name=name, source="extracted", evidence=explicit[:200]))
            continue
        for pattern in patterns:
            cue = _first_line_with(lines, pattern)
            if cue:
                items.append(SkillItem(name=name, source="inferred", evidence=f"Suggested by: “{cue[:160]}”"))
                break
    return items


# --- experience, projects, education ------------------------------------------------------------


def _split_title(header: str) -> tuple[str, str | None, str | None]:
    period = None
    match = _YEAR_RANGE.search(header) or _SINGLE_YEAR.search(header)
    if match:
        period = match.group(0).strip("() ")
        header = (header[: match.start()] + header[match.end():]).strip(" ,|-–—()")
    for separator in (" — ", " – ", " - ", " | ", " at ", ", "):
        if separator in header:
            title, organization = header.split(separator, 1)
            return title.strip()[:300], organization.strip(" ,|-–—")[:200] or None, period
    return header[:300], None, period


def _group_entries(lines: list[tuple[str, bool]]) -> list[tuple[str, list[str]]]:
    entries: list[tuple[str, list[str]]] = []
    for line, bullet in lines:
        sentence_like = line.endswith(".") and len(line.split()) > 6 and not _YEAR_RANGE.search(line)
        if entries and (bullet or _RESPONSIBILITY_RE.match(line) or sentence_like):
            entries[-1][1].append(line[:300])
        else:
            entries.append((line, []))
    return entries


def extract_experience(section: list[tuple[str, bool]]) -> list[ExperienceEntry]:
    result = []
    for header, details in _group_entries(section)[:15]:
        title, organization, period = _split_title(header)
        if not title:
            continue
        result.append(ExperienceEntry(title=title, organization=organization, period=period,
                                      responsibilities=details[:8], source="extracted"))
    return result


def extract_projects(section: list[tuple[str, bool]]) -> list[ProjectEntry]:
    vocabulary = load_skills(get_settings().skills_list_path)
    result = []
    for header, details in _group_entries(section)[:15]:
        separator = re.search(r":| - | — | – ", header)
        name, rest = (header[: separator.start()], header[separator.end():]) if separator else (header, "")
        description = " ".join([rest.strip(), *details]).strip()[:600] or None
        technologies = find_skills(f"{header} {' '.join(details)}", vocabulary, limit=20)
        result.append(ProjectEntry(name=name.strip()[:150] or header[:150], description=description,
                                   technologies=technologies, source="extracted"))
    return result


# --- years and level -----------------------------------------------------------------------------


def estimate_years(section_lines: list[str], full_text: str) -> YearsValue:
    stated = _YEARS_STATED.search(full_text)
    if stated:
        return YearsValue(value=float(stated.group(1)), source="extracted", evidence=stated.group(0))
    this_year = date.today().year
    spans = []
    singles = 0
    for line in section_lines:
        for match in _YEAR_RANGE.finditer(line):
            start = int(match.group(2))
            end_raw = match.group(4).lower()
            end = this_year if end_raw in ("present", "current", "now", "today") else int(end_raw)
            if 1980 <= start <= end <= this_year + 1:
                spans.append((start, end))
        if not _YEAR_RANGE.search(line) and _SINGLE_YEAR.search(line):
            singles += 1
    if not spans and not singles:
        return YearsValue()
    # Merge overlapping ranges so parallel jobs are not double counted.
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    years = sum(max(0.5, end - start) for start, end in merged) + 0.5 * singles
    years = round(min(years, 40.0), 1)
    parts = []
    if merged:
        parts.append(f"{len(spans)} date range(s)")
    if singles:
        parts.append(f"{singles} single-year role(s) counted as half a year each")
    return YearsValue(value=years, source="inferred",
                      evidence=f"Estimated from {' and '.join(parts)} in the Experience section.")


def infer_level(years: YearsValue, full_text: str, experience: list[ExperienceEntry]) -> LevelValue:
    titles = " ".join(e.title for e in experience)
    if _SENIOR_TITLE_RE.search(titles) and (years.value is None or years.value >= 4):
        return LevelValue(value="senior", source="inferred", evidence=f"Senior/lead job title: {titles[:120]}")
    student = _STUDENT_RE.search(full_text)
    if student and (years.value is None or years.value < 3):
        return LevelValue(value="student", source="inferred",
                          evidence=f"CV mentions “{student.group(0)}” (internships and part-time roles are not counted as full-time experience).")
    if years.value is not None and years.value < 3 and experience and all(
        re.search(r"\b(intern|trainee|assistant|volunteer)\b", e.title, re.IGNORECASE) for e in experience
    ):
        return LevelValue(value="entry", source="inferred", evidence="Experience consists of internships or assistant roles.")
    if years.value is None:
        if student:
            return LevelValue(value="student", source="inferred", evidence=f"CV mentions “{student.group(0)}”.")
        if experience:
            return LevelValue(value="entry", source="inferred",
                              evidence="Experience entries found but no dates; assumed entry level.")
        return LevelValue()
    y = years.value
    if y < 1:
        level = "student" if student else "entry"
    elif y < 2:
        level = "junior"
    elif y < 5:
        level = "mid"
    else:
        level = "senior"
    return LevelValue(value=level, source="inferred", evidence=f"About {y:g} year(s) of experience.")


# --- role, expertise, achievements -------------------------------------------------------------


def infer_target_role(header_lines: list[str], skill_names: list[str]) -> InferredValue:
    for line in header_lines[:4]:
        exact = [role for role in roles() if re.search(rf"\b{re.escape(role)}\b", line, re.IGNORECASE)]
        if exact:
            return InferredValue(value=exact[0], source="inferred", evidence=f"CV headline: “{line[:100]}”.")
    for line in header_lines[:4]:
        matched = match_roles(line) if len(line) <= 60 else set()
        if len(matched) == 1:
            role = next(iter(matched))
            return InferredValue(value=role, source="inferred", evidence=f"CV headline: “{line[:100]}”.")
    best, best_hits, best_total = None, 0, 0
    owned = {s.lower() for s in skill_names}
    for name, spec in roles().items():
        hits = sum(1 for s in spec.required_skills if s.lower() in owned)
        if hits > best_hits:
            best, best_hits, best_total = name, hits, len(spec.required_skills)
    if best and best_hits >= 3:
        return InferredValue(value=best, source="inferred",
                             evidence=f"Your skills match {best_hits} of {best_total} core skills for {best}.")
    return InferredValue()


def infer_expertise(skills: list[SkillItem]) -> list[SkillItem]:
    by_category: dict[str, list[str]] = {}
    for skill in skills:
        if skill.category:
            by_category.setdefault(skill.category, []).append(skill.name)
    areas = []
    for category, names in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        if len(names) >= 3:
            areas.append(SkillItem(name=category, source="inferred",
                                   evidence=f"{len(names)} skills in this area: {', '.join(names[:5])}."))
    return areas[:15]


def extract_achievements(sections: dict[str, list[tuple[str, bool]]]) -> list[TextItem]:
    candidates = [line for name in ("achievements", "certifications") for line, _ in sections.get(name, [])]
    for name in ("experience", "projects", "summary", "header"):
        candidates += [line for line, _ in sections.get(name, []) if _ACHIEVEMENT_RE.search(line)]
    unique = list(dict.fromkeys(candidates))
    return [TextItem(text=line[:300], source="extracted", evidence="Found in the CV.") for line in unique[:15]]


# --- entry point ------------------------------------------------------------------------------


def build_profile(text: str | None, *, explicit_target_role: str | None = None) -> ProfileData:
    """Build a profile from CV text. Never raises on odd input; problems become warnings."""
    text = (text or "").replace("\x00", " ")
    warnings: list[str] = []
    if len(text.strip()) < 50:
        warnings.append("Very little text could be read from the CV, so the profile is mostly empty.")
    sections = split_sections(text)
    lines = [line for section in sections.values() for line, _ in section]

    technical = extract_technical_skills(text, lines)
    experience = extract_experience(sections.get("experience", []))
    projects = extract_projects(sections.get("projects", []))
    education = [TextItem(text=line[:300], source="extracted") for line, _ in sections.get("education", [])[:10]]
    interests = [TextItem(text=line[:300], source="extracted")
                 for name in ("summary", "interests") for line, _ in sections.get(name, [])][:10]
    years = estimate_years([line for line, _ in sections.get("experience", [])], text)
    level = infer_level(years, text, experience)

    if explicit_target_role:
        target = InferredValue(value=explicit_target_role[:100], source="user", evidence="Chosen by you.")
    else:
        target = infer_target_role([line for line, _ in sections.get("header", [])], [s.name for s in technical])

    for name, label in (("experience", "Experience"), ("education", "Education"), ("projects", "Projects")):
        if not sections.get(name):
            warnings.append(f"No {label} section was found. Add it during review if it applies to you.")
    if not technical:
        warnings.append("No known technical skills were found. Add your skills during review.")
    if level.value is None:
        warnings.append("Your experience level could not be determined. Please choose it during review.")
    if target.value is None:
        warnings.append("No target role could be inferred. Choose one during review or at interview setup.")

    return ProfileData(
        target_role=target,
        experience_level=level,
        years_experience=years,
        technical_skills=technical,
        soft_skills=extract_soft_skills(text, lines),
        expertise_areas=infer_expertise(technical),
        experience=experience,
        education=education,
        projects=projects,
        achievements=extract_achievements(sections),
        career_interests=interests,
        warnings=warnings[:20],
    )


def target_role_requirements(profile: ProfileData):
    role = profile.target_role.value
    return role_requirements(match_roles(role)) if role else None
