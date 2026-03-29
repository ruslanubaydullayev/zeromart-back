"""Admin moderation: approve, reject with reason."""

import html

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from database import Database
from posting import send_ad_media
from states import AdminFlow

router = Router(name="admin")


def _admin_ids() -> frozenset[int]:
    return settings.admin_ids


def _parse_mod_callback(data: str) -> tuple[str, int] | None:
    # mod:approve:12 / mod:reject:12
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "mod":
        return None
    action = parts[1]
    try:
        ad_id = int(parts[2])
    except ValueError:
        return None
    if action not in ("approve", "reject"):
        return None
    return action, ad_id


@router.callback_query(F.data.startswith("mod:"))
async def moderation_callback(cq: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    if cq.from_user.id not in _admin_ids():
        await cq.answer()
        return

    parsed = _parse_mod_callback(cq.data)
    if not parsed:
        await cq.answer()
        return

    action, ad_id = parsed
    ad = await db.get_ad(ad_id)
    if not ad or ad.status != "pending":
        await cq.answer("Объявление уже обработано.", show_alert=True)
        return

    if action == "reject":
        await cq.answer()
        await state.set_state(AdminFlow.wait_reject_reason)
        await state.update_data(reject_ad_id=ad_id)
        await cq.message.answer("Отклонение: отправьте одним сообщением причину для продавца.")
        return

    # approve
    if not settings.channel_id:
        await cq.answer("CHANNEL_ID не настроен в .env", show_alert=True)
        return

    media = await db.get_ad_media(ad_id)
    try:
        msgs = await send_ad_media(
            bot,
            settings.channel_id,
            ad,
            media,
            reply_markup=None,
            caption_prefix=None,
        )
    except Exception:
        await cq.answer("Не удалось опубликовать. Проверьте права бота в канале.", show_alert=True)
        return

    first_id = msgs[0].message_id if msgs else None
    await db.set_ad_status(ad_id, "approved", channel_message_id=first_id)
    await bot.send_message(ad.user_id, "Ваше объявление одобрено и опубликовано в канале.")
    await cq.answer("Опубликовано")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.message(AdminFlow.wait_reject_reason, F.text)
async def admin_reject_reason(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    if message.from_user.id not in _admin_ids():
        return
    if message.text.startswith("/"):
        return

    data = await state.get_data()
    ad_id = int(data["reject_ad_id"])
    ad = await db.get_ad(ad_id)
    if not ad or ad.status != "pending":
        await state.clear()
        await message.answer("Это объявление уже обработано.")
        return

    reason = message.text.strip()
    if not reason:
        await message.answer("Нужен непустой текст причины.")
        return

    await db.set_ad_status(ad_id, "rejected")
    await db.add_rejection(ad_id, reason)
    await bot.send_message(
        ad.user_id,
        f"Объявление отклонено.\nПричина: {html.escape(reason)}",
    )
    await state.clear()
    await message.answer("Отклонение сохранено, продавец уведомлён.")
