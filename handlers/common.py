"""Shared commands: /start, /cancel."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import settings
from database import Database
from keyboards import contact_keyboard
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

    await message.answer(
        "Добро пожаловать в маркетплейс. Чтобы подать объявление, поделитесь номером телефона.",
        reply_markup=contact_keyboard(),
    )
    await state.set_state(SellerFlow.wait_phone)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Сейчас нет активного сценария. Нажмите /start.")
        return
    await state.clear()
    await message.answer("Сценарий сброшен. Снова нажмите /start, чтобы подать объявление.")
