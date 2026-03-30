"""Shared commands: /start, /cancel."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import settings
from database import Database
from keyboards import contact_keyboard, main_menu_keyboard
from states import SellerFlow

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    uid = message.from_user.id
    username = message.from_user.username
    name = message.from_user.full_name
    await db.upsert_user(uid, phone=None, username=username, display_name=name)

    if uid in settings.admin_ids:
        await message.answer(
            "Вы администратор. Новые объявления приходят сюда с кнопками "
            "<b>Одобрить</b> / <b>Отклонить</b>."
        )
        return

    if await db.user_has_phone(uid):
        await message.answer(
            "С возвращением! Номер у нас уже сохранён — повторно делиться им не нужно.\n"
            "Нажмите <b>Подать объявление</b> в меню ниже.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        "Добро пожаловать в маркетплейс. Чтобы подать объявление, поделитесь номером телефона.",
        reply_markup=contact_keyboard(),
    )
    await state.set_state(SellerFlow.wait_phone)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Сейчас нет активного сценария.")
        return
    await state.clear()
    uid = message.from_user.id
    if uid not in settings.admin_ids and await db.user_has_phone(uid):
        await message.answer(
            "Сценарий сброшен. Чтобы снова подать объявление — кнопка в меню.",
            reply_markup=main_menu_keyboard(),
        )
        return
    await message.answer("Сценарий сброшен. Нажмите /start.")
