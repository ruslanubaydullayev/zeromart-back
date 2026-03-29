"""Send ads to Telegram chats (channel or admin)."""

from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InputMediaPhoto, InputMediaVideo, Message

from database import AdRecord, MediaItem
from formatting import build_channel_caption


def _caption_for_ad(ad: AdRecord, prefix: str | None = None) -> str:
    body = build_channel_caption(
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

    msgs = await bot.send_media_group(chat_id, media=bundle)
    if reply_markup is not None:
        tail = await bot.send_message(
            chat_id,
            f"#{ad.id} · {ad.title[:80]}",
            reply_markup=reply_markup,
        )
        return [*msgs, tail]
    return list(msgs)
