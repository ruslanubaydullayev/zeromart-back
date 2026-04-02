"""Reply and inline keyboards (localized)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from language import CATEGORY_SLUGS, DISTRICT_SLUGS, tr


def wizard_nav_reply_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=tr(locale, "back")),
        KeyboardButton(text=tr(locale, "home")),
    )
    return builder.as_markup(resize_keyboard=True)


def wizard_media_reply_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=tr(locale, "next")))
    builder.row(
        KeyboardButton(text=tr(locale, "back")),
        KeyboardButton(text=tr(locale, "home")),
    )
    return builder.as_markup(resize_keyboard=True)


def wizard_phone_reply_keyboard(locale: str | None, *, with_registered: bool) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if with_registered:
        builder.row(KeyboardButton(text=tr(locale, "reg_phone")))
    builder.row(
        KeyboardButton(text=tr(locale, "back")),
        KeyboardButton(text=tr(locale, "home")),
    )
    return builder.as_markup(resize_keyboard=True)


def main_menu_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=tr(locale, "menu_submit")))
    builder.add(KeyboardButton(text=tr(locale, "menu_my_ads")))
    builder.add(KeyboardButton(text=tr(locale, "menu_change_language")))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def admin_menu_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=tr(locale, "menu_admin_stats")))
    builder.row(KeyboardButton(text=tr(locale, "menu_change_language")))
    return builder.as_markup(resize_keyboard=True)


def contact_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=tr(locale, "share_contact"), request_contact=True))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def language_choose_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr("ru", "lang_button_ru"), callback_data="lang:set:ru"),
        InlineKeyboardButton(text=tr("uz", "lang_button_uz"), callback_data="lang:set:uz"),
    )
    return b.as_markup()


def category_reply_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for slug in CATEGORY_SLUGS:
        builder.add(KeyboardButton(text=tr(locale, f"cat_{slug}")))
    builder.adjust(2)
    builder.row(
        KeyboardButton(text=tr(locale, "back")),
        KeyboardButton(text=tr(locale, "home")),
    )
    return builder.as_markup(resize_keyboard=True)


def region_reply_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=tr(locale, "region_tashkent")))
    builder.row(
        KeyboardButton(text=tr(locale, "back")),
        KeyboardButton(text=tr(locale, "home")),
    )
    return builder.as_markup(resize_keyboard=True)


def rayon_tashkent_reply_keyboard(locale: str | None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for slug in DISTRICT_SLUGS:
        builder.add(KeyboardButton(text=tr(locale, f"district_{slug}")))
    builder.adjust(2)
    builder.row(
        KeyboardButton(text=tr(locale, "back")),
        KeyboardButton(text=tr(locale, "home")),
    )
    return builder.as_markup(resize_keyboard=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)


def confirm_ad_keyboard(locale: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=tr(locale, "confirm_send"), callback_data="ad:confirm"),
        InlineKeyboardButton(text=tr(locale, "confirm_cancel"), callback_data="ad:cancel"),
    )
    builder.row(
        InlineKeyboardButton(text=tr(locale, "back"), callback_data="wiz:back"),
        InlineKeyboardButton(text=tr(locale, "home"), callback_data="wiz:home"),
    )
    return builder.as_markup()


def admin_moderate_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Одобрить", callback_data=f"mod:approve:{ad_id}"),
        InlineKeyboardButton(text="Отклонить", callback_data=f"mod:reject:{ad_id}"),
    )
    return builder.as_markup()


def admin_reject_options_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="С комментарием", callback_data=f"mod:reject_reason:{ad_id}"),
        InlineKeyboardButton(text="Без комментария", callback_data=f"mod:reject_skip:{ad_id}"),
    )
    return builder.as_markup()
