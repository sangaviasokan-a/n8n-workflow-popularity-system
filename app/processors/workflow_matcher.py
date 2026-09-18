from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any


# Words that describe the presentation of a workflow rather than its identity.
STOP_WORDS = {
    "how", "to", "the", "a", "an", "and", "or", "for", "of", "in", "on", "at",
    "with", "using", "use", "via", "from", "into", "this", "that", "your", "my",
    "tutorial", "tutorials", "guide", "guides", "step", "steps", "learn", "learning",
    "course", "courses", "complete", "full", "ultimate", "best", "easy", "simple",
    "beginner", "beginners", "advanced", "free", "new", "latest", "setup", "set", "up",
    "build", "building", "built", "create", "creating", "created", "make", "making", "made",
    "automation", "automations", "workflow", "workflows", "example", "examples", "project",
    "projects", "video", "videos", "hour", "hours", "day", "days", "no", "code", "nocode",
    "powered", "powering", "solution", "solutions", "template", "templates",
}

PLATFORM_WORDS = {"n8n"}

# Canonical aliases are applied before matching.  Keep this intentionally small:
# over-normalization creates false positives between unrelated workflows.
ALIASES = {
    "aiagent": "ai agent",
    "aiagents": "ai agents",
    "googlesheets": "google sheets",
    "googlecalendar": "google calendar",
    "googledrive": "google drive",
    "whatsappbusiness": "whatsapp business",
    "linkedinapi": "linkedin api",
}

# Distinct product/integration domains should not be merged merely because they
# share generic words such as "automation", "ai", or "agent".
DOMAIN_GROUPS = (
    frozenset({"gmail"}),
    frozenset({"outlook", "microsoft outlook"}),
    frozenset({"whatsapp"}),
    frozenset({"telegram"}),
    frozenset({"slack"}),
    frozenset({"discord"}),
    frozenset({"linkedin"}),
    frozenset({"google sheets", "googlesheets"}),
    frozenset({"google drive", "googledrive"}),
    frozenset({"google calendar", "googlecalendar"}),
    frozenset({"notion"}),
    frozenset({"hubspot"}),
    frozenset({"salesforce"}),
)


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _alias_words(words: list[str]) -> list[str]:
    result: list[str] = []
    i = 0
    while i < len(words):
        # Join common concatenated aliases first.
        joined = words[i]
        if i + 1 < len(words):
            pair = joined + words[i + 1]
            if pair in ALIASES:
                result.extend(ALIASES[pair].split())
                i += 2
                continue
        replacement = ALIASES.get(joined)
        if replacement:
            result.extend(replacement.split())
        else:
            result.append(joined)
        i += 1
    return result


def _canonical_topic_words(title: str) -> list[str]:
    value = _normalize_text(title)
    if not value:
        return []
    words = _alias_words(value.split())
    cleaned: list[str] = []
    for word in words:
        if word in STOP_WORDS:
            continue
        # Safe singularization for common workflow nouns.
        if word.endswith("ies") and len(word) > 4:
            word = word[:-3] + "y"
        elif word.endswith("s") and len(word) > 3 and word not in {"sheets", "news"}:
            word = word[:-1]
        if word and word not in STOP_WORDS:
            cleaned.append(word)
    # Stable de-duplication.
    return list(dict.fromkeys(cleaned))


def build_workflow_key(title: str) -> str:
    if not isinstance(title, str):
        return ""
    words = _canonical_topic_words(title)
    if not words:
        return ""
    platform = [w for w in words if w in PLATFORM_WORDS]
    topic = [w for w in words if w not in PLATFORM_WORDS]
    return " ".join(platform + topic)


def assign_workflow_key(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    title = record.get("title") or record.get("keyword") or ""
    result["workflow_key"] = build_workflow_key(str(title))
    return result


def workflow_tokens(value: str) -> set[str]:
    return set(build_workflow_key(value).split()) if value else set()


def _contains_phrase(value: str, phrase: str) -> bool:
    return f" {value} ".find(f" {phrase} ") >= 0


def workflow_domains(value: str) -> set[str]:
    normalized = build_workflow_key(value)
    tokens = set(normalized.split())
    domains: set[str] = set()
    for group in DOMAIN_GROUPS:
        for domain in group:
            if " " in domain:
                if _contains_phrase(normalized, domain):
                    domains.add(domain.split()[0])
            elif domain in tokens:
                domains.add(domain)
    return domains


def has_domain_conflict(first: str, second: str) -> bool:
    a, b = workflow_domains(first), workflow_domains(second)
    return bool(a and b and a.isdisjoint(b))


def token_similarity(first: str, second: str) -> float:
    a, b = workflow_tokens(first), workflow_tokens(second)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def sequence_similarity(first: str, second: str) -> float:
    return SequenceMatcher(None, build_workflow_key(first), build_workflow_key(second)).ratio()


def workflows_match(first: str, second: str, first_platform: str | None = None, second_platform: str | None = None) -> bool:
    a = build_workflow_key(first)
    b = build_workflow_key(second)
    if not a or not b:
        return False
    if a == b:
        return True
    if has_domain_conflict(a, b):
        return False
    at, bt = workflow_tokens(a), workflow_tokens(b)
    if not at or not bt:
        return False
    overlap = len(at & bt)
    union = len(at | bt)
    jaccard = overlap / union
    containment = overlap / min(len(at), len(bt))
    seq = sequence_similarity(a, b)
    # Generic n8n-only keys are not meaningful identities.
    topic_a = at - PLATFORM_WORDS
    topic_b = bt - PLATFORM_WORDS
    if not topic_a or not topic_b:
        return False
    # Require a meaningful shared topic. Short keys are deliberately stricter.
    if len(topic_a) <= 1 or len(topic_b) <= 1:
        return containment >= 1.0
    return containment >= 0.80 or (jaccard >= 0.60 and seq >= 0.78)


def workflow_match_score(first: str, second: str) -> float:
    a = build_workflow_key(first)
    b = build_workflow_key(second)
    if not a or not b or has_domain_conflict(a, b):
        return 0.0
    if a == b:
        return 1.0
    at, bt = workflow_tokens(a), workflow_tokens(b)
    overlap = len(at & bt)
    if not overlap:
        return 0.0
    jaccard = overlap / len(at | bt)
    containment = overlap / min(len(at), len(bt))
    seq = sequence_similarity(a, b)
    return max(jaccard, containment * 0.9, seq * 0.75)


def find_best_workflow_match(candidates: list[Any], incoming_key: str, incoming_platform: str | None = None) -> tuple[Any | None, float]:
    best = None
    best_score = 0.0
    for candidate in candidates:
        key = getattr(candidate, "workflow_key", "")
        platform = None
        try:
            source_platforms = {s.platform for s in candidate.sources}
            if incoming_platform and source_platforms:
                platform = next(iter(source_platforms))
        except Exception:
            pass
        if not workflows_match(incoming_key, key, incoming_platform, platform):
            continue
        score = workflow_match_score(incoming_key, key)
        if score > best_score:
            best, best_score = candidate, score
    return best, best_score
