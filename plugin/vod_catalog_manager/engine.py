from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MAX_PATTERN_LENGTH = 256
MAX_SYNC_BATCH = 500
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

@dataclass(frozen=True)
class RegexRule:
    pattern: str
    replacement: str = ""
    flags: int = re.IGNORECASE
    enabled: bool = True

def validate_pattern(pattern: str) -> None:
    if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
        raise ValueError(f"Pattern is required and must be <= {MAX_PATTERN_LENGTH} characters")
    if re.search(r"\([^)]*[+*][^)]*\)[+*{]", pattern):
        raise ValueError("Potentially catastrophic nested quantifier rejected")
    if re.search(r"(\.\*|\.\+){2,}", pattern):
        raise ValueError("Potentially catastrophic wildcard repetition rejected")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex: {exc}") from exc

def normalize_digits(value: str) -> str:
    return value.translate(ARABIC_DIGITS)

def normalize_unicode(value: str) -> str:
    return unicodedata.normalize("NFKC", normalize_digits(value)).replace("\u200b", "").replace("\ufeff", "")

def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()

def normalize_title(value: str) -> str:
    value = normalize_unicode(value).replace("_", " ")
    value = re.sub(r"\s*\|+\s*", " - ", value)
    return normalize_whitespace(value)

def apply_rule(value: str, rule: RegexRule) -> str:
    if not rule.enabled:
        return normalize_title(value)
    validate_pattern(rule.pattern)
    return normalize_title(re.sub(rule.pattern, rule.replacement, value, flags=rule.flags))

def safe_filename(value: str, max_len: int = 180) -> str:
    value = normalize_title(value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", value)
    value = normalize_whitespace(value)
    value = re.sub(r"\s+\.", ".", value)
    return value.rstrip(". ")[:max_len].rstrip(". ")

DEFAULT_RECIPES = [
    {"id":"arabic-digits","name":"Arabic/Persian digits","pattern":r"[٠-٩۰-۹]","replacement":"","explanation":"Normalize digits before identity matching."},
    {"id":"season-episode-en","name":"Season/Episode to S01E02","pattern":r"(?i)\bseason\s*(\d+)\s+episode\s*(\d+)\b","replacement":r"S\g<1>E\g<2>","explanation":"Normalizes common English season/episode labels."},
    {"id":"season-episode-ar","name":"Arabic season/episode","pattern":r"(?i)\b(?:الموسم|موسم)\s*(\d+)\s*(?:الحلقة|حلقة)\s*(\d+)\b","replacement":r"S\g<1>E\g<2>","explanation":"Converts common Arabic labels to SxxExx."},
    {"id":"resolution","name":"Remove resolution tag","pattern":r"\s*\[(?:2160p|4K|1080p|720p|576p|480p)\]\s*","replacement":" ","explanation":"Use when the resolution belongs to release metadata rather than the title."},
    {"id":"quality","name":"Remove release quality","pattern":r"\s*\b(?:WEB-DL|WEBRip|BluRay|BRRip|HDRip|HDTV|REMUX)\b","replacement":" ","explanation":"Removes common release/source labels."},
    {"id":"codec","name":"Remove codec","pattern":r"\s*\b(?:x264|x265|h264|h265|HEVC|AVC|VP9|AV1)\b","replacement":" ","explanation":"Removes codec labels from display names."},
    {"id":"provider-brackets","name":"Remove provider bracket","pattern":r"\s*\[(?:VIP|FHD|HD|4K|NETFLIX|AMAZON|PROVIDER)[^\]]*\]","replacement":"","explanation":"Remove known provider labels only after previewing."},
    {"id":"pipes","name":"Normalize separators","pattern":r"\s*\|+\s*","replacement":" - ","explanation":"Turns provider pipe separators into readable dashes."},
    {"id":"dots","name":"Filename dots to spaces","pattern":r"(?<=\w)\.(?=\w)","replacement":" ","explanation":"Useful for release-style filenames."},
    {"id":"spaces","name":"Collapse whitespace","pattern":r"\s{2,}","replacement":" ","explanation":"Final presentation cleanup."},
]
