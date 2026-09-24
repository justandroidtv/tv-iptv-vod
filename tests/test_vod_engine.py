import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugin" / "vod_catalog_manager"
sys.path.insert(0, str(PLUGIN_DIR))

from engine import RegexRule, apply_rule, normalize_title, safe_filename, validate_pattern

def test_normalize_arabic_digits():
    assert normalize_title("  فيلم ١٢٣__") == "فيلم 123"

def test_regex_nested_quantifier_rejected():
    try:
        validate_pattern(r"(a+)+$")
    except ValueError as exc:
        assert "catastrophic" in str(exc)
    else:
        raise AssertionError("unsafe pattern accepted")

def test_regex_replacement():
    rule = RegexRule(r"season\s*(\d+)", r"S\g<1>")
    assert apply_rule("Show Season 2", rule) == "Show S2"

def test_filename_sanitization():
    assert safe_filename("A:/Bad*Movie?.mp4") == "A Bad Movie.mp4"
