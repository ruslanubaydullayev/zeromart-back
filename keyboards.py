"""Reply and inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Главное меню продавца (тексты должны совпадать везде)
SUBMIT_AD_TEXT = "Разместить объявление"
MY_ADS_TEXT = "Мои объявления"

# Reply-клавиша на шаге медиа (под полем ввода)
NEXT_STEP_TEXT = "Дальше"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=SUBMIT_AD_TEXT))
    builder.add(KeyboardButton(text=MY_ADS_TEXT))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def contact_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Поделиться телефоном", request_contact=True))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)


def media_next_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=NEXT_STEP_TEXT))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


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
