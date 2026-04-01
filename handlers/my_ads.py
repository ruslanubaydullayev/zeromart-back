"""Продавец: список объявлений и снятие с публикации / отметка доставки."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database import AdRecord, Database
from keyboards import main_menu_keyboard
from language import all_variant_texts, normalize_locale, tr
from posting import mark_ad_as_found_owner, try_delete_ad_from_channel

router = Router(name="my_ads")


def _status_local(locale: str | None, status: str) -> str:
    loc = normalize_locale(locale)
    return {
        "pending": tr(loc, "status_pending"),
        "approved": tr(loc, "status_approved"),
        "rejected": tr(loc, "status_rejected"),
        "delivered": tr(loc, "status_delivered"),
        "withdrawn": tr(loc, "status_withdrawn"),
    }.get(status, status)


def _ad_summary_line(locale: str | None, ad: AdRecord) -> str:
    ts = datetime.fromtimestamp(ad.created_at).strftime("%d.%m.%Y %H:%M")
    title = ad.title.replace("\n", " ").strip()
    if len(title) > 80:
        title = title[:80] + "…"
    st = _status_local(locale, ad.status)
    return f"#{ad.id} · {title}\n{st} · {ts}"


def _owner_actions_keyboard(locale: str | None, ad: AdRecord) -> InlineKeyboardBuilder | None:
    loc = normalize_locale(locale)
    if ad.status == "pending":
        b = InlineKeyboardBuilder()
        b.row(
            InlineKeyboardButton(
                text=tr(loc, "myad_withdraw_pending"),
                callback_data=f"myad:withdraw:{ad.id}",
            )
        )
        return b
    if ad.status == "approved":
        b = InlineKeyboardBuilder()
        b.row(
            InlineKeyboardButton(
                text=tr(loc, "myad_delivered"),
                callback_data=f"myad:delivered:{ad.id}",
            ),
            InlineKeyboardButton(
                text=tr(loc, "myad_withdraw_pending"),
                callback_data=f"myad:withdraw:{ad.id}",
            ),
        )
        return b
    return None


@router.message(F.text.in_(all_variant_texts("menu_my_ads")))
async def open_my_ads(message: Message, state: FSMContext, db: Database) -> None:
    lang = normalize_locale(await db.get_user_lang(message.from_user.id))
    if message.from_user.id in settings.admin_ids:
        await message.answer(tr(lang, "my_ads_sellers_only"))
        return
    if not await db.user_has_phone(message.from_user.id):
        await message.answer(tr(lang, "my_ads_need_phone"))
        return

    await state.clear()
    uid = message.from_user.id
    ads = await db.list_user_ads_recent(uid, limit=15)
    if not ads:
        await message.answer(
            tr(lang, "my_ads_empty", submit=tr(lang, "menu_submit")),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    await message.answer(
        tr(lang, "my_ads_intro"),
        reply_markup=main_menu_keyboard(lang),
    )
    for ad in ads:
        text = _ad_summary_line(lang, ad)
        kb = _owner_actions_keyboard(lang, ad)
        if kb is not None:
            await message.answer(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text)


@router.callback_query(F.data.startswith("myad:"))
async def my_ad_action(cq: CallbackQuery, db: Database, bot: Bot) -> None:
    uid = cq.from_user.id
    lang = normalize_locale(await db.get_user_lang(uid))
    parts = cq.data.split(":")
    if len(parts) != 3 or parts[0] != "myad":
        await cq.answer()
        return
    action, ad_id_s = parts[1], parts[2]
    try:
        ad_id = int(ad_id_s)
    except ValueError:
        await cq.answer()
        return

    ad = await db.get_ad(ad_id)
    if not ad or ad.user_id != uid:
        await cq.answer("Объявление не найдено.", show_alert=True)
        return

    if action == "delivered":
        if ad.status != "approved":
            await cq.answer("Действие недоступно для этого статуса.", show_alert=True)
            return
        await mark_ad_as_found_owner(bot, settings.channel_id, ad)
        await db.set_ad_status(ad_id, "delivered")
        await cq.answer("Отмечено: доставлено")
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cq.message.answer(
            tr(lang, "myad_done_delivered", id=ad_id),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    if action == "withdraw":
        if ad.status not in ("pending", "approved"):
            await cq.answer("Уже закрыто.", show_alert=True)
            return
        if ad.status == "approved":
            await try_delete_ad_from_channel(bot, settings.channel_id, ad)
        await db.set_ad_status(ad_id, "withdrawn")
        await cq.answer("Снято с продажи")
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        note = (
            tr(lang, "myad_done_withdraw_pending", id=ad_id)
            if ad.status == "pending"
            else tr(lang, "myad_done_withdraw_channel", id=ad_id)
        )
        await cq.message.answer(note, reply_markup=main_menu_keyboard(lang))
        return

    await cq.answer()
