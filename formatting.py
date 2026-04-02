"""Channel caption and seller summary (localized)."""

from __future__ import annotations

import html

from language import category_label, normalize_locale, tr


def escape(text: str) -> str:
    return html.escape(text.strip(), quote=False)


def build_channel_caption(
    category: str,
    title: str,
    region: str,
    rayon: str,
    comment: str,
    phone: str,
    *,
    ad_status: str,
    locale: str | None = None,
    show_phone: bool | None = None,
) -> str:
    """Подпись для канала/модерации: статус и категория на языке продавца."""
    loc = normalize_locale(locale)
    if show_phone is None:
        show_phone = ad_status in ("pending", "approved")
    status_text = tr(loc, f"channel_status_{ad_status}")
    cat_label = category_label(loc, category)
    phone_val = escape(phone) if show_phone else escape(tr(loc, "channel_phone_hidden"))
    lines = [
        f"📌 <b>{escape(status_text)}</b>",
        tr(loc, "channel_line_title", value=escape(title)),
        tr(loc, "channel_line_category", value=escape(cat_label)),
        tr(loc, "channel_line_region", value=escape(region)),
        tr(loc, "channel_line_rayon", value=escape(rayon)),
        tr(loc, "channel_line_comment", value=escape(comment)),
        tr(loc, "channel_line_phone", value=phone_val),
    ]
    return "\n".join(lines)


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
