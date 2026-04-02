"""Shared commands: /start, /cancel."""

import html

from aiogram import F
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from config import settings
from database import Database
from keyboards import admin_menu_keyboard, contact_keyboard, language_choose_keyboard, main_menu_keyboard
from language import all_variant_texts, normalize_locale, tr
from states import SellerFlow

router = Router(name="common")


def _welcome_display_name(user: User | None) -> str:
    if not user:
        return html.escape("…")
    raw = (user.full_name or user.first_name or "").strip()
    return html.escape(raw) if raw else html.escape("…")


def _welcome_return_text(lang: str, user: User | None) -> str:
    loc = normalize_locale(lang)
    name = _welcome_display_name(user)
    if loc == "uz":
        return tr(loc, "welcome_return", name=name)
    return tr(
        loc,
        "welcome_return",
        name=name,
        submit=tr(loc, "menu_submit"),
        my_ads=tr(loc, "menu_my_ads"),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    uid = message.from_user.id
    username = message.from_user.username
    name = message.from_user.full_name
    await db.upsert_user(uid, phone=None, lang=None, username=username, display_name=name)

    if uid in settings.admin_ids:
        alang = normalize_locale(await db.get_user_lang(uid))
        await message.answer(
            tr(alang, "admin_welcome"),
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(alang),
        )
        return

    lang = normalize_locale(await db.get_user_lang(uid))
    if not await db.get_user_lang(uid):
        await message.answer(
            tr(lang, "start_choose_language"),
            reply_markup=language_choose_keyboard(),
        )
        return

    if await db.user_has_phone(uid):
        await message.answer(
            _welcome_return_text(lang, message.from_user),
            reply_markup=main_menu_keyboard(lang),
            parse_mode="HTML",
        )
        return

    await message.answer(
        tr(lang, "welcome_share_phone"),
        reply_markup=contact_keyboard(lang),
    )
    await state.set_state(SellerFlow.wait_phone)


@router.callback_query(lambda cq: cq.data and cq.data.startswith("lang:set:"))
async def set_language(cq: CallbackQuery, state: FSMContext, db: Database) -> None:
    parts = (cq.data or "").split(":")
    if len(parts) != 3:
        await cq.answer()
        return
    lang = normalize_locale(parts[2])
    uid = cq.from_user.id
    await db.upsert_user(uid, phone=None, lang=lang, username=cq.from_user.username, display_name=cq.from_user.full_name)
    await state.clear()
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if uid in settings.admin_ids:
        await cq.message.answer(
            tr(lang, "admin_welcome"),
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(lang),
        )
        return

    if await db.user_has_phone(uid):
        await cq.message.answer(
            _welcome_return_text(lang, cq.from_user),
            reply_markup=main_menu_keyboard(lang),
            parse_mode="HTML",
        )
        return

    await cq.message.answer(
        tr(lang, "welcome_share_phone"),
        reply_markup=contact_keyboard(lang),
    )
    await state.set_state(SellerFlow.wait_phone)


@router.message(F.text.in_(all_variant_texts("menu_change_language")))
async def change_language_from_menu(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    lang = normalize_locale(await db.get_user_lang(message.from_user.id))
    await message.answer(
        tr(lang, "start_choose_language"),
        reply_markup=language_choose_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database) -> None:
    current = await state.get_state()
    if current is None:
        lang = normalize_locale(await db.get_user_lang(message.from_user.id))
        if message.from_user.id in settings.admin_ids:
            await message.answer(
                tr(lang, "cmd_cancel_none"),
                reply_markup=admin_menu_keyboard(lang),
            )
            return
        await message.answer(tr(lang, "cmd_cancel_none"))
        return
    await state.clear()
    uid = message.from_user.id
    if uid in settings.admin_ids:
        alang = normalize_locale(await db.get_user_lang(uid))
        await message.answer(
            tr(alang, "cmd_cancel_done_menu"),
            reply_markup=admin_menu_keyboard(alang),
        )
        return
    if await db.user_has_phone(uid):
        lang = normalize_locale(await db.get_user_lang(uid))
        await message.answer(
            tr(lang, "cmd_cancel_done_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return
    await message.answer(tr("ru", "cmd_cancel_done_start"))
