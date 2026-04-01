"""Load UI strings from JSON; supported locales: ru, uz."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES: tuple[str, ...] = ("ru", "uz")
DEFAULT_LOCALE = "ru"

# Canonical values stored in DB / channel (English category slug, place names)
CATEGORY_SLUGS: tuple[str, ...] = (
    "electronics",
    "clothing",
    "home",
    "books",
    "toys",
    "sports",
    "pet",
    "other",
)

REGION_TASHKENT = "Tashkent"

DISTRICT_SLUGS: tuple[str, ...] = (
    "olmazor",
    "bektemir",
    "mirobod",
    "mirzo_ulugbek",
    "sergeli",
    "uchtepa",
    "chilonzor",
    "shayhontoxur",
    "yunusobod",
    "yakkasaroy",
    "yashnobod",
)

_DISTRICT_CANONICAL: dict[str, str] = {
    "olmazor": "Olmazor",
    "bektemir": "Bektemir",
    "mirobod": "Mirobod",
    "mirzo_ulugbek": "Mirzo-Ulugbek",
    "sergeli": "Sergeli",
    "uchtepa": "Uchtepa",
    "chilonzor": "Chilonzor",
    "shayhontoxur": "Shayhontoxur",
    "yunusobod": "Yunusobod",
    "yakkasaroy": "Yakkasaroy",
    "yashnobod": "Yashnobod",
}


def district_canonical(slug: str) -> str:
    return _DISTRICT_CANONICAL.get(slug, slug)


def district_slug_from_canonical(name: str) -> str | None:
    for s, c in _DISTRICT_CANONICAL.items():
        if c == name:
            return s
    return None


@lru_cache(maxsize=8)
def _load_locale(code: str) -> dict[str, str]:
    code = code if code in LOCALES else DEFAULT_LOCALE
    path = Path(__file__).resolve().parent / f"{code}.json"
    with path.open(encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)
    return {k: str(v) for k, v in raw.items()}


def normalize_locale(code: str | None) -> str:
    if not code:
        return DEFAULT_LOCALE
    c = code.strip().lower()
    if c in ("uzb", "uz-latn", "uz_latn"):
        return "uz"
    if c in LOCALES:
        return c
    return DEFAULT_LOCALE


def tr(locale: str | None, key: str, **kwargs: Any) -> str:
    loc = normalize_locale(locale)
    table = _load_locale(loc)
    s = table.get(key) or _load_locale(DEFAULT_LOCALE).get(key) or key
    if kwargs:
        try:
            return s.format(**kwargs)
        except KeyError:
            return s
    return s


def all_variant_texts(key: str) -> frozenset[str]:
    """All localized strings for a key (for F.text matching)."""
    out: set[str] = set()
    for loc in LOCALES:
        t = tr(loc, key).strip()
        if t:
            out.add(t)
    return frozenset(out)


def all_category_button_texts() -> frozenset[str]:
    s: set[str] = set()
    for loc in LOCALES:
        for slug in CATEGORY_SLUGS:
            t = tr(loc, f"cat_{slug}").strip()
            if t:
                s.add(t)
    return frozenset(s)


def category_slug_from_button_text(text: str) -> str | None:
    t = text.strip()
    for slug in CATEGORY_SLUGS:
        for loc in LOCALES:
            if tr(loc, f"cat_{slug}").strip() == t:
                return slug
    return None


def all_district_button_texts() -> frozenset[str]:
    s: set[str] = set()
    for loc in LOCALES:
        for slug in DISTRICT_SLUGS:
            key = f"district_{slug}"
            x = tr(loc, key).strip()
            if x:
                s.add(x)
    return frozenset(s)


def district_slug_from_button_text(text: str) -> str | None:
    t = text.strip()
    for slug in DISTRICT_SLUGS:
        for loc in LOCALES:
            if tr(loc, f"district_{slug}").strip() == t:
                return slug
    return None


def category_label(locale: str | None, slug: str) -> str:
    return tr(locale, f"cat_{slug}")


def district_label(locale: str | None, slug: str) -> str:
    return tr(locale, f"district_{slug}")


def channel_category_line(slug: str) -> str:
    """Single language for public channel caption (Russian)."""
    return tr("ru", f"cat_{slug}")
