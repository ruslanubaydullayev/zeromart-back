"""Продавец: список объявлений и снятие с публикации / отметка доставки."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database import AdRecord, Database
from keyboards import MY_ADS_TEXT, main_menu_keyboard
from posting import try_delete_ad_from_channel

router = Router(name="my_ads")


def _status_ru(status: str) -> str:
    return {
        "pending": "на модерации",
        "approved": "в канале",
        "rejected": "отклонено",
        "delivered": "товар доставлен",
        "withdrawn": "снято с продажи",
    }.get(status, status)


def _ad_summary_line(ad: AdRecord) -> str:
    ts = datetime.fromtimestamp(ad.created_at).strftime("%d.%m.%Y %H:%M")
    title = ad.title.replace("\n", " ").strip()
    if len(title) > 80:
        title = title[:80] + "…"
    st = _status_ru(ad.status)
    return f"#{ad.id} · {title}\n{st} · {ts}"


def _owner_actions_keyboard(ad: AdRecord) -> InlineKeyboardBuilder | None:
    if ad.status == "pending":
        b = InlineKeyboardBuilder()
        b.row(
            InlineKeyboardButton(
                text="Не хочу продавать",
                callback_data=f"myad:withdraw:{ad.id}",
            )
        )
        return b
    if ad.status == "approved":
        b = InlineKeyboardBuilder()
        b.row(
            InlineKeyboardButton(
                text="Товар доставлен",
                callback_data=f"myad:delivered:{ad.id}",
            ),
            InlineKeyboardButton(
                text="Не хочу продавать",
                callback_data=f"myad:withdraw:{ad.id}",
            ),
        )
        return b
    return None


@router.message(F.text == MY_ADS_TEXT)
async def open_my_ads(message: Message, state: FSMContext, db: Database) -> None:
    if message.from_user.id in settings.admin_ids:
        await message.answer("Раздел для продавцов.")
        return
    if not await db.user_has_phone(message.from_user.id):
        await message.answer("Сначала /start и номер телефона.")
        return

    await state.clear()
    uid = message.from_user.id
    ads = await db.list_user_ads_recent(uid, limit=15)
    if not ads:
        await message.answer(
            "У вас пока нет объявлений. Нажмите «Разместить объявление».",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        "Ваши недавние объявления\n\n"
        "Ниже — по одному сообщению на объявление; кнопки только там, где можно действовать.",
        reply_markup=main_menu_keyboard(),
    )
    for ad in ads:
        text = _ad_summary_line(ad)
        kb = _owner_actions_keyboard(ad)
        if kb is not None:
            await message.answer(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text)


@router.callback_query(F.data.startswith("myad:"))
async def my_ad_action(cq: CallbackQuery, db: Database, bot: Bot) -> None:
    uid = cq.from_user.id
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
        await try_delete_ad_from_channel(bot, settings.channel_id, ad)
        await db.set_ad_status(ad_id, "delivered")
        await cq.answer("Отмечено: доставлено")
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cq.message.answer(
            f"Объявление #{ad_id} отмечено как доставленное. Пост в канале снят (если бот мог его удалить).",
            reply_markup=main_menu_keyboard(),
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
            f"Объявление #{ad_id} снято."
            if ad.status == "pending"
            else f"Объявление #{ad_id} снято; пост в канале удалён (если возможно)."
        )
        await cq.message.answer(note, reply_markup=main_menu_keyboard())
        return

    await cq.answer()
