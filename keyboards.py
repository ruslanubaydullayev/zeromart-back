"""Reply and inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Текст кнопки главного меню продавца (должен совпадать везде)
SUBMIT_AD_TEXT = "Подать объявление"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=SUBMIT_AD_TEXT))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def contact_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Поделиться телефоном", request_contact=True))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)


def listing_media_next_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Дальше", callback_data="listing_media:done"))
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
