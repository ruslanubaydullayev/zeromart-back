"""Admin moderation: approve, reject with reason."""

import html
import json
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from database import Database
from keyboards import admin_reject_options_keyboard, main_menu_keyboard
from language import normalize_locale, tr
from posting import send_ad_media
from states import AdminFlow

router = Router(name="admin")

logger = logging.getLogger(__name__)


def _publish_error_hint(exc: BaseException) -> str:
    if isinstance(exc, TelegramForbiddenError):
        return (
            "Доступ запрещён. Добавьте бота в канал как администратора "
            "и включите право «Публиковать сообщения»."
        )
    if isinstance(exc, TelegramAPIError):
        msg = str(exc).lower()
        if "chat not found" in msg or "channel not found" in msg:
            return (
                "Канал не найден. Проверьте CHANNEL_ID: @публичный_канал "
                "или число -100… для приватного канала."
            )
        if "not enough rights" in msg or "have no rights" in msg:
            return "Недостаточно прав в канале: разрешите боту публиковать сообщения."
        if "wrong file identifier" in msg or "wrong remote file identifier" in msg:
            return "Файлы объявления недействительны. Создайте объявление заново."
        if "caption" in msg and ("parse" in msg or "entity" in msg or "html" in msg):
            return "Ошибка в HTML-тексте поста (редко). Сообщите разработчику."
    return f"Не удалось опубликовать: {str(exc)[:150]}"


def _admin_ids() -> frozenset[int]:
    return settings.admin_ids


def _parse_mod_callback(data: str) -> tuple[str, int] | None:
    # mod:approve:12 / mod:reject:12 / mod:reject_reason:12 / mod:reject_skip:12
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "mod":
        return None
    action = parts[1] if len(parts) == 3 else f"{parts[1]}_{parts[2]}"
    try:
        ad_id = int(parts[-1])
    except ValueError:
        return None
    if action not in ("approve", "reject", "reject_reason", "reject_skip"):
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
        await cq.message.answer(
            "Отклонение: выбрать с комментарием или без.",
            reply_markup=admin_reject_options_keyboard(ad_id),
        )
        return

    if action == "reject_reason":
        await cq.answer()
        await state.set_state(AdminFlow.wait_reject_reason)
        await state.update_data(reject_ad_id=ad_id)
        await cq.message.answer("Отправьте одним сообщением причину для продавца.")
        return

    if action == "reject_skip":
        await cq.answer("Отклонено")
        await db.set_ad_status(ad_id, "rejected")
        await db.add_rejection(ad_id, "Без комментария")
        user_lang = normalize_locale(await db.get_user_lang(ad.user_id))
        await bot.send_message(
            ad.user_id,
            tr(user_lang, "ad_rejected_no_reason"),
            reply_markup=main_menu_keyboard(user_lang),
        )
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
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
    except Exception as e:
        logger.exception(
            "Publish to channel failed ad_id=%s channel=%r",
            ad_id,
            settings.channel_id,
        )
        await cq.answer(_publish_error_hint(e), show_alert=True)
        return

    ids = [m.message_id for m in msgs]
    first_id = ids[0] if ids else None
    ids_json = json.dumps(ids) if ids else None
    await db.set_ad_status(
        ad_id,
        "approved",
        channel_message_id=first_id,
        channel_message_ids_json=ids_json,
    )
    user_lang = normalize_locale(await db.get_user_lang(ad.user_id))
    await bot.send_message(
        ad.user_id,
        tr(user_lang, "ad_approved_published"),
        reply_markup=main_menu_keyboard(user_lang),
    )
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
    user_lang = normalize_locale(await db.get_user_lang(ad.user_id))
    await bot.send_message(
        ad.user_id,
        tr(user_lang, "ad_rejected_with_reason", reason=html.escape(reason)),
        reply_markup=main_menu_keyboard(user_lang),
    )
    await state.clear()
    await message.answer("Отклонение сохранено, продавец уведомлён.")
