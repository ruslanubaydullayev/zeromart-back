"""Reply and inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def contact_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Поделиться телефоном", request_contact=True))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)


def media_done_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Дальше (фото готовы)", callback_data="media:photos_done"))
    builder.adjust(1)
    return builder.as_markup()


def skip_video_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Без видео", callback_data="media:skip_video"))
    return builder.as_markup()


def confirm_ad_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Отправить", callback_data="ad:confirm"),
        InlineKeyboardButton(text="Отмена", callback_data="ad:cancel"),
    )
    return builder.as_markup()


def admin_moderate_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Одобрить", callback_data=f"mod:approve:{ad_id}"),
        InlineKeyboardButton(text="Отклонить", callback_data=f"mod:reject:{ad_id}"),
    )
    return builder.as_markup()
