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
    phone_line = (
        f"📞 {escape(phone)}"
        if show_phone
        else f"📞 {escape(tr(loc, 'channel_phone_hidden'))}"
    )
    cat_label = category_label(loc, category)
    return (
        f"📌 <b>{escape(status_text)}</b>\n\n"
        f"{escape(tr(loc, 'caption_category', label=cat_label))}\n\n"
        f"<b>{escape(title)}</b>\n\n"
        f"📍 {escape(region)}, {escape(rayon)}\n\n"
        f"{escape(comment)}\n\n"
        f"{phone_line}"
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
