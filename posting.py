"""Send ads to Telegram chats (channel or admin)."""

from __future__ import annotations

import json
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputMediaPhoto, InputMediaVideo, Message

from database import AdRecord, MediaItem
from formatting import build_channel_caption

logger = logging.getLogger(__name__)


def _channel_message_ids(ad: AdRecord) -> list[int]:
    ids: list[int] = []
    raw = ad.channel_message_ids
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                ids = [int(x) for x in parsed if x is not None]
        except (json.JSONDecodeError, TypeError, ValueError):
            ids = []
    if not ids and ad.channel_message_id is not None:
        ids = [ad.channel_message_id]
    return ids


async def sync_channel_post_caption(bot: Bot, chat_id: str | int, ad: AdRecord) -> None:
    """Обновляет подпись первого сообщения поста в канале (статус + скрытие телефона)."""
    if chat_id is None or chat_id == "":
        return
    ids = _channel_message_ids(ad)
    if not ids:
        return
    msg_id = ids[0]
    caption = _truncate_caption(_caption_for_ad(ad))
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=msg_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    except TelegramAPIError:
        try:
            await bot.edit_message_text(
                text=caption,
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode=ParseMode.HTML,
            )
        except TelegramAPIError as e:
            logger.warning("Не удалось обновить пост в канале ad=%s: %s", ad.id, e)


async def sync_moderation_post_caption(bot: Bot, message: Message, ad: AdRecord) -> None:
    """Обновляет подпись сообщения у админа (после одобрения — «в канале», а не «на модерации»)."""
    prefix = f"🛂 Модерация · #{ad.id}"
    caption = _truncate_caption(_caption_for_ad(ad, prefix))
    chat_id = message.chat.id
    msg_id = message.message_id
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=msg_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    except TelegramAPIError:
        try:
            await bot.edit_message_text(
                text=caption,
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode=ParseMode.HTML,
            )
        except TelegramAPIError as e:
            logger.warning("Не удалось обновить модерацию ad=%s: %s", ad.id, e)


def _caption_for_ad(
    ad: AdRecord,
    prefix: str | None = None,
    *,
    caption_status: str | None = None,
) -> str:
    st = caption_status if caption_status is not None else ad.status
    body = build_channel_caption(
        ad.category,
        ad.title,
        ad.region,
        ad.rayon,
        ad.comment,
        ad.phone,
        ad_status=st,
    )
    if prefix:
        return f"{prefix}\n\n{body}"
    return body


def _truncate_caption(caption: str, max_len: int = 1000) -> str:
    if len(caption) <= max_len:
        return caption
    return caption[: max_len - 1] + "…"


async def send_ad_media(
    bot: Bot,
    chat_id: str | int,
    ad: AdRecord,
    media: list[MediaItem],
    reply_markup=None,
    caption_prefix: str | None = None,
    caption_status: str | None = None,
) -> list[Message]:
    """Post ad visuals + caption. Returns sent messages (for channel_message_id)."""
    caption = _truncate_caption(
        _caption_for_ad(ad, caption_prefix, caption_status=caption_status)
    )
    parse = ParseMode.HTML

    if not media:
        msg = await bot.send_message(
            chat_id,
            caption,
            parse_mode=parse,
            reply_markup=reply_markup,
        )
        return [msg]

    bundle: list[InputMediaPhoto | InputMediaVideo] = []
    for idx, item in enumerate(media):
        cap = caption if idx == 0 else None
        if item.kind == "photo":
            bundle.append(
                InputMediaPhoto(media=item.file_id, caption=cap, parse_mode=parse if cap else None)
            )
        else:
            bundle.append(
                InputMediaVideo(media=item.file_id, caption=cap, parse_mode=parse if cap else None)
            )

    if len(bundle) == 1:
        single = bundle[0]
        if isinstance(single, InputMediaPhoto):
            msg = await bot.send_photo(
                chat_id,
                single.media,
                caption=single.caption,
                parse_mode=parse,
                reply_markup=reply_markup,
            )
        else:
            msg = await bot.send_video(
                chat_id,
                single.media,
                caption=single.caption,
                parse_mode=parse,
                reply_markup=reply_markup,
            )
        return [msg]

    if reply_markup is not None:
        first = bundle[0]
        sent: list[Message] = []
        if isinstance(first, InputMediaPhoto):
            primary = await bot.send_photo(
                chat_id,
                first.media,
                caption=first.caption,
                parse_mode=parse,
                reply_markup=reply_markup,
            )
        else:
            primary = await bot.send_video(
                chat_id,
                first.media,
                caption=first.caption,
                parse_mode=parse,
                reply_markup=reply_markup,
            )
        sent.append(primary)

        rest = bundle[1:]
        if rest:
            stripped: list[InputMediaPhoto | InputMediaVideo] = []
            for x in rest:
                if isinstance(x, InputMediaPhoto):
                    stripped.append(InputMediaPhoto(media=x.media))
                else:
                    stripped.append(InputMediaVideo(media=x.media))
            more = await bot.send_media_group(chat_id, media=stripped)
            sent.extend(list(more))
        return sent

    msgs = await bot.send_media_group(chat_id, media=bundle)
    return list(msgs)
