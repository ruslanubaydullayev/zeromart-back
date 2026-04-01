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


async def try_delete_ad_from_channel(bot: Bot, chat_id: str | int, ad: AdRecord) -> None:
    """Удаляет все сообщения поста в канале (альбом = несколько message_id)."""
    if chat_id is None or chat_id == "":
        return
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
    for mid in ids:
        try:
            await bot.delete_message(chat_id, mid)
        except TelegramAPIError as e:
            logger.warning("Не удалить сообщение %s в канале: %s", mid, e)


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


async def mark_ad_as_found_owner(
    bot: Bot,
    chat_id: str | int,
    ad: AdRecord,
    *,
    marker_text: str = "Нашел свой владелец",
) -> None:
    """Adds sold marker to the existing channel ad message."""
    if chat_id is None or chat_id == "":
        return
    ids = _channel_message_ids(ad)
    if not ids:
        return
    msg_id = ids[0]
    marker_line = f"✅ {marker_text}"
    base_caption = _truncate_caption(_caption_for_ad(ad))
    updated_caption = _truncate_caption(f"{base_caption}\n\n{marker_line}")
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=msg_id,
            caption=updated_caption,
            parse_mode=ParseMode.HTML,
        )
    except TelegramAPIError:
        try:
            await bot.edit_message_text(
                text=updated_caption,
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode=ParseMode.HTML,
            )
        except TelegramAPIError as e:
            logger.warning("Не удалось пометить продажу в сообщении ad=%s: %s", ad.id, e)


def _caption_for_ad(ad: AdRecord, prefix: str | None = None) -> str:
    body = build_channel_caption(
        ad.category,
        ad.title,
        ad.region,
        ad.rayon,
        ad.comment,
        ad.phone,
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
) -> list[Message]:
    """Post ad visuals + caption. Returns sent messages (for channel_message_id)."""
    caption = _truncate_caption(_caption_for_ad(ad, caption_prefix))
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
