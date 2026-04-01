"""Reply and inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Главное меню продавца (тексты должны совпадать везде)
SUBMIT_AD_TEXT = "Разместить объявление"
MY_ADS_TEXT = "Мои объявления"

# Reply-клавиша на шаге медиа (под полем ввода)
NEXT_STEP_TEXT = "Дальше"

# Навигация мастера (тексты фиксированы)
WIZARD_BACK_TEXT = "◀️ Назад"
WIZARD_HOME_TEXT = "🏠 Главная"
REG_PHONE_REPLY_TEXT = "📱 Номер из регистрации"


def wizard_nav_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=WIZARD_BACK_TEXT),
        KeyboardButton(text=WIZARD_HOME_TEXT),
    )
    return builder.as_markup(resize_keyboard=True)


def wizard_media_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=NEXT_STEP_TEXT))
    builder.row(
        KeyboardButton(text=WIZARD_BACK_TEXT),
        KeyboardButton(text=WIZARD_HOME_TEXT),
    )
    return builder.as_markup(resize_keyboard=True)


def wizard_phone_reply_keyboard(*, with_registered: bool) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if with_registered:
        builder.row(KeyboardButton(text=REG_PHONE_REPLY_TEXT))
    builder.row(
        KeyboardButton(text=WIZARD_BACK_TEXT),
        KeyboardButton(text=WIZARD_HOME_TEXT),
    )
    return builder.as_markup(resize_keyboard=True)


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


def confirm_ad_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Отправить", callback_data="ad:confirm"),
        InlineKeyboardButton(text="Отмена", callback_data="ad:cancel"),
    )
    builder.row(
        InlineKeyboardButton(text=WIZARD_BACK_TEXT, callback_data="wiz:back"),
        InlineKeyboardButton(text=WIZARD_HOME_TEXT, callback_data="wiz:home"),
    )
    return builder.as_markup()


def admin_moderate_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Одобрить", callback_data=f"mod:approve:{ad_id}"),
        InlineKeyboardButton(text="Отклонить", callback_data=f"mod:reject:{ad_id}"),
    )
    return builder.as_markup()
