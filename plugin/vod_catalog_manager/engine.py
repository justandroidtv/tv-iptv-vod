from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

MAX_PATTERN_LENGTH = 256
MAX_SYNC_BATCH = 500
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ALIAS_FIELDS = {"title", "year", "category", "resolution", "audio", "subtitles"}


@dataclass(frozen=True)
class RegexRule:
    pattern: str
    replacement: str = ""
    flags: int = re.IGNORECASE
    enabled: bool = True
    stop: bool = False


def validate_pattern(pattern: str) -> None:
    if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
        raise ValueError(
            f"Pattern is required and must be <= {MAX_PATTERN_LENGTH} characters"
        )
    if re.search(r"\([^)]*[+*][^)]*\)[+*{]", pattern):
        raise ValueError("Potentially catastrophic nested quantifier rejected")
    if re.search(r"(\.\*|\.\+){2,}", pattern):
        raise ValueError("Potentially catastrophic wildcard repetition rejected")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex: {exc}") from exc


def compile_rule(rule: RegexRule) -> re.Pattern[str]:
    if not isinstance(rule, RegexRule):
        raise TypeError("rule must be a RegexRule")
    validate_pattern(rule.pattern)
    return re.compile(rule.pattern, rule.flags)


def normalize_digits(value: str) -> str:
    return value.translate(ARABIC_DIGITS)


def normalize_unicode(value: str) -> str:
    return unicodedata.normalize(
        "NFKC", normalize_digits(value)
    ).replace("\u200b", "").replace("\ufeff", "")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value: str) -> str:
    value = normalize_unicode(value).replace("_", " ")
    value = re.sub(r"\s*\|+\s*", " - ", value)
    return normalize_whitespace(value)


def apply_rules(value: str, rules: list[RegexRule]) -> str:
    result = str(value)
    for rule in rules:
        if not rule.enabled:
            continue
        result = compile_rule(rule).sub(rule.replacement, result)
        result = normalize_unicode(result)
        if rule.stop:
            break
    return normalize_title(result)


def apply_rule(value: str, rule: RegexRule) -> str:
    return apply_rules(value, [rule])


def safe_filename(value: str, max_len: int = 180) -> str:
    if max_len < 1:
        raise ValueError("max_len must be positive")
    value = normalize_title(value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", value)
    value = normalize_whitespace(value)
    value = re.sub(r"\s+\.", ".", value)
    value = value.rstrip(". ")
    return value[:max_len].rstrip(". ")


def render_alias(
    template: str,
    *,
    title: str,
    year: Any = "",
    category: str = "",
    resolution: str = "",
    audio: str = "",
    subtitles: str = "",
) -> str:
    fields = {
        "title": title,
        "year": year or "",
        "category": category or "",
        "resolution": resolution or "",
        "audio": audio or "",
        "subtitles": subtitles or "",
    }
    unknown = {
        match.group(1)
        for match in re.finditer(r"{([^{}]+)}", str(template))
        if match.group(1) not in ALIAS_FIELDS
    }
    if unknown:
        raise ValueError(f"Unknown alias field: {sorted(unknown)[0]}")
    try:
        return normalize_title(str(template).format(**fields))
    except (KeyError, ValueError, IndexError) as exc:
        raise ValueError("Invalid alias template") from exc


def profile_matches(source: dict[str, Any], profile: dict[str, Any]) -> bool:
    categories = {
        str(x).casefold() for x in profile.get("categories", []) if x
    }
    excluded = {
        str(x).casefold()
        for x in profile.get("excluded_categories", [])
        if x
    }
    category = str(source.get("category") or "").casefold()
    if categories and category not in categories:
        return False
    if category in excluded:
        return False

    resolution = int(source.get("resolution") or 0)
    minimum = int(profile.get("min_resolution") or 0)
    maximum = int(profile.get("max_resolution") or 99999)
    if resolution and not minimum <= resolution <= maximum:
        return False

    for source_key, profile_key in (
        ("audio", "required_audio"),
        ("subtitles", "required_subtitles"),
    ):
        required = {
            str(x).casefold() for x in profile.get(profile_key, []) if x
        }
        values = {
            str(x).casefold() for x in (source.get(source_key) or []) if x
        }
        if required and not required.intersection(values):
            return False
    return True


def rank_source(source: dict[str, Any], profile: dict[str, Any]) -> tuple:
    preferred_audio = [
        str(x).casefold() for x in profile.get("preferred_audio", []) if x
    ]
    preferred_subs = [
        str(x).casefold() for x in profile.get("preferred_subtitles", []) if x
    ]
    audio = {
        str(x).casefold() for x in (source.get("audio") or []) if x
    }
    subs = {
        str(x).casefold() for x in (source.get("subtitles") or []) if x
    }

    audio_rank = min(
        (preferred_audio.index(x) for x in audio if x in preferred_audio),
        default=999,
    )
    sub_rank = min(
        (preferred_subs.index(x) for x in subs if x in preferred_subs),
        default=999,
    )
    metadata_rank = 0 if source.get("metadata_known") else 1
    resolution_rank = -int(source.get("resolution") or 0)
    bitrate_rank = -int(source.get("bitrate") or 0)
    return (
        audio_rank,
        sub_rank,
        metadata_rank,
        resolution_rank,
        bitrate_rank,
    )


DEFAULT_RECIPES = [
    {
        "id": "season-episode-en",
        "name": "Season/Episode → S01E02",
        "pattern": r"(?i)\bseason\s*(\d+)\s+episode\s*(\d+)\b",
        "replacement": r"S\g<1>E\g<2>",
        "explanation": "Normalize common English season/episode labels.",
    },
    {
        "id": "season-episode-ar",
        "name": "الموسم/الحلقة → S01E02",
        "pattern": r"(?i)\b(?:الموسم|موسم)\s*(\d+)\s*(?:الحلقة|حلقة)\s*(\d+)\b",
        "replacement": r"S\g<1>E\g<2>",
        "explanation": "Convert common Arabic season/episode labels.",
    },
    {
        "id": "resolution",
        "name": "Remove resolution tag",
        "pattern": r"\s*\[(?:2160p|4K|1080p|720p|576p|480p)\]\s*",
        "replacement": " ",
        "explanation": "Use when resolution is release metadata, not part of the title.",
    },
    {
        "id": "quality",
        "name": "Remove release quality",
        "pattern": r"\s*\b(?:WEB-DL|WEBRip|BluRay|BRRip|HDRip|HDTV|REMUX)\b",
        "replacement": " ",
        "explanation": "Remove common release/source labels.",
    },
    {
        "id": "codec",
        "name": "Remove codec",
        "pattern": r"\s*\b(?:x264|x265|h264|h265|HEVC|AVC|VP9|AV1)\b",
        "replacement": " ",
        "explanation": "Remove codec labels from display names.",
    },
    {
        "id": "provider-brackets",
        "name": "Remove provider bracket",
        "pattern": r"\s*\[(?:VIP|FHD|HD|4K|NETFLIX|AMAZON|PROVIDER)[^\]]*\]",
        "replacement": "",
        "explanation": "Remove known provider labels only after previewing.",
    },
    {
        "id": "year-suffix",
        "name": "Normalize trailing year",
        "pattern": r"\s*[\(\[]?(19\d{2}|20\d{2})[\)\]]?\s*$",
        "replacement": r" (\g<1>)",
        "explanation": "Normalize a release year at the end of a title.",
    },
    {
        "id": "pipes",
        "name": "Normalize separators",
        "pattern": r"\s*\|+\s*",
        "replacement": " - ",
        "explanation": "Convert provider pipe separators into readable dashes.",
    },
    {
        "id": "dots",
        "name": "Filename dots to spaces",
        "pattern": r"(?<=\w)\.(?=\w)",
        "replacement": " ",
        "explanation": "Useful for release-style filename titles.",
    },
    {
        "id": "empty-brackets",
        "name": "Remove empty brackets",
        "pattern": r"\s*[\[\(]\s*[\]\)]\s*",
        "replacement": " ",
        "explanation": "Clean empty bracket pairs after other rules.",
    },
    {
        "id": "tmdb-tag",
        "name": "Remove TMDB tag",
        "pattern": r"\s*[\{\[]tmdb(?:id)?[-:]\d+[\}\]]",
        "replacement": "",
        "explanation": "Remove explicit TMDB folder tags from display names.",
    },
    {
        "id": "episode-padding",
        "name": "Pad single-digit episode",
        "pattern": r"(?i)\bS(\d{1,2})E(\d)\b",
        "replacement": r"S\g<1>E0\g<2>",
        "explanation": "Normalize S1E2 to S1E02.",
    },
    {
        "id": "season-padding",
        "name": "Pad single-digit season",
        "pattern": r"(?i)\bS(\d)E(\d{2})\b",
        "replacement": r"S0\g<1>E\g<2>",
        "explanation": "Normalize S1E02 to S01E02.",
    },
    {
        "id": "dash-spacing",
        "name": "Normalize dash spacing",
        "pattern": r"\s*[-–—]\s*",
        "replacement": " - ",
        "explanation": "Normalize ASCII and Unicode dash spacing.",
    },
    {
        "id": "aka",
        "name": "Normalize AKA",
        "pattern": r"(?i)\s*\b(?:aka|also known as)\s*",
        "replacement": " - ",
        "explanation": "Normalize common alternate-title separators.",
    },
    {
        "id": "spaces",
        "name": "Collapse whitespace",
        "pattern": r"\s{2,}",
        "replacement": " ",
        "explanation": "Final presentation cleanup.",
    },
]
