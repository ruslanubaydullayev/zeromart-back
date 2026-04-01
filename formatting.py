"""Channel caption and seller summary (localized)."""

from __future__ import annotations

import html

from language import category_label, channel_category_line, tr


def escape(text: str) -> str:
    return html.escape(text.strip(), quote=False)


def build_channel_caption(
    category: str,
    title: str,
    region: str,
    rayon: str,
    comment: str,
    phone: str,
) -> str:
    return (
        f"{escape(tr('ru', 'caption_category', label=channel_category_line(category)))}\n\n"
        f"<b>{escape(title)}</b>\n\n"
        f"📍 {escape(region)}, {escape(rayon)}\n\n"
        f"{escape(comment)}\n\n"
        f"📞 {escape(phone)}"
    )


def build_summary_for_seller(
    locale: str | None,
    category: str,
    title: str,
    region: str,
    rayon: str,
    comment: str,
    phone: str,
) -> str:
    return (
        f"{tr(locale, 'summary_header')}\n\n"
        f"{tr(locale, 'summary_category', value=escape(category_label(locale, category)))}\n"
        f"{tr(locale, 'summary_title', value=escape(title))}\n"
        f"{tr(locale, 'summary_region', value=escape(region))}\n"
        f"{tr(locale, 'summary_rayon', value=escape(rayon))}\n"
        f"{tr(locale, 'summary_comment', value=escape(comment))}\n"
        f"{tr(locale, 'summary_phone', value=escape(phone))}"
    )
