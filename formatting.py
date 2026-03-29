"""Channel caption and HTML escaping."""

from __future__ import annotations

import html


def escape(text: str) -> str:
    return html.escape(text.strip(), quote=False)


def build_channel_caption(title: str, region: str, rayon: str, comment: str, phone: str) -> str:
    return (
        f"<b>{escape(title)}</b>\n\n"
        f"📍 {escape(region)}, {escape(rayon)}\n\n"
        f"{escape(comment)}\n\n"
        f"📞 {escape(phone)}"
    )


def build_summary_for_seller(
    title: str,
    region: str,
    rayon: str,
    comment: str,
    phone: str,
) -> str:
    return (
        "<b>Проверьте объявление</b>\n\n"
        f"Заголовок: {escape(title)}\n"
        f"Регион: {escape(region)}\n"
        f"Район: {escape(rayon)}\n"
        f"Описание: {escape(comment)}\n"
        f"Телефон: {escape(phone)}"
    )
