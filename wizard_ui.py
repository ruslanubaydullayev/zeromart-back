"""Один активный «вопрос» бота: удаляем предыдущий prompt и при необходимости ответ пользователя."""

from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup

WIZARD_PROMPT_KEY = "wizard_prompt_id"


async def _safe_delete(bot: Bot, chat_id: int, message_id: int | None) -> None:
    # History mode: we keep chat history and do not delete messages.
    return


async def wizard_replace_prompt(
    message: Message,
    state: FSMContext,
    text: str,
    *,
    reply_markup: ReplyKeyboardMarkup | InlineKeyboardMarkup | None = None,
    parse_mode: str | ParseMode | None = ParseMode.HTML,
    delete_user_message_id: int | None = None,
) -> Message:
    """Удаляет старый prompt бота, опционально сообщение пользователя, шлёт новый prompt."""
    bot = message.bot
    chat_id = message.chat.id
    try:
        await bot.send_chat_action(chat_id, "typing")
    except Exception:
        pass
    data = await state.get_data()
    old_id = data.get(WIZARD_PROMPT_KEY)
    await _safe_delete(bot, chat_id, old_id)
    await _safe_delete(bot, chat_id, delete_user_message_id)
    sent = await message.answer(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
    await state.update_data(**{WIZARD_PROMPT_KEY: sent.message_id})
    return sent


async def wizard_delete_prompt_only(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _safe_delete(message.bot, message.chat.id, data.get(WIZARD_PROMPT_KEY))
    await state.update_data(**{WIZARD_PROMPT_KEY: None})


async def wizard_finish_clear_prompt(message: Message, state: FSMContext) -> None:
    await wizard_delete_prompt_only(message, state)


async def go_wizard_home(
    message: Message,
    state: FSMContext,
    *,
    delete_user_message_id: int | None = None,
    answer_text: str = "Главное меню.",
    reply_markup: ReplyKeyboardMarkup | None = None,
) -> None:
    data = await state.get_data()
    await _safe_delete(message.bot, message.chat.id, data.get(WIZARD_PROMPT_KEY))
    await _safe_delete(message.bot, message.chat.id, delete_user_message_id)
    await state.clear()
    await message.answer(answer_text, reply_markup=reply_markup)
