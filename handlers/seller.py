"""Seller flow: phone, photos, optional video, text fields, confirm."""

from __future__ import annotations

import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from config import settings
from database import Database, MediaItem
from formatting import build_summary_for_seller
from keyboards import (
    confirm_ad_keyboard,
    contact_keyboard,
    media_done_keyboard,
    remove_keyboard,
    skip_video_keyboard,
)
from posting import send_ad_media
from states import SellerFlow

router = Router(name="seller")

MAX_PHOTOS = 3
MAX_TITLE = 120
MAX_REGION = 80
MAX_RAYON = 80
MAX_COMMENT = 1500
MAX_PHONE = 40


@router.message(SellerFlow.wait_phone, F.contact)
async def seller_phone(message: Message, state: FSMContext, db: Database) -> None:
    phone = message.contact.phone_number
    uid = message.from_user.id
    await db.upsert_user(
        uid,
        phone=phone,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
    )
    await state.update_data(reg_phone=phone, photos=[])
    await message.answer(
        "Спасибо. Отправьте от 1 до 3 фото.",
        reply_markup=remove_keyboard(),
    )
    await message.answer(
        "Когда фото будут готовы — нажмите кнопку ниже.",
        reply_markup=media_done_keyboard(),
    )
    await state.set_state(SellerFlow.wait_media)


@router.message(SellerFlow.wait_phone)
async def seller_phone_required(message: Message) -> None:
    await message.answer(
        "Нужен номер из Telegram — нажмите «Поделиться телефоном».",
        reply_markup=contact_keyboard(),
    )


@router.message(SellerFlow.wait_media, F.photo)
async def seller_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = list(data.get("photos", []))
    if len(photos) >= MAX_PHOTOS:
        await message.answer(
            f"Уже {MAX_PHOTOS} фото. Нажмите «Дальше» или /cancel.",
            reply_markup=media_done_keyboard(),
        )
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(
        f"Фото {len(photos)}/{MAX_PHOTOS}. Можно добавить ещё или нажать «Дальше (фото готовы)».",
        reply_markup=media_done_keyboard(),
    )


@router.message(SellerFlow.wait_media, F.video)
async def seller_video_before_photos(message: Message) -> None:
    await message.answer("Сначала отправьте 1–3 фото. Видео будет на следующем шаге.")


@router.callback_query(SellerFlow.wait_media, F.data == "media:photos_done")
async def seller_photos_done(cq: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) < 1:
        await cq.answer("Нужно минимум одно фото.", show_alert=True)
        return
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(SellerFlow.wait_video)
    await cq.message.answer(
        "Пришлите видео (необязательно) или нажмите «Без видео».",
        reply_markup=skip_video_keyboard(),
    )


@router.callback_query(SellerFlow.wait_video, F.data == "media:skip_video")
async def seller_skip_video_cb(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(video=None)
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(SellerFlow.wait_title)
    await cq.message.answer("Введите заголовок объявления (кратко, для канала):")


@router.message(SellerFlow.wait_video, F.video)
async def seller_video(message: Message, state: FSMContext) -> None:
    await state.update_data(video=message.video.file_id)
    await state.set_state(SellerFlow.wait_title)
    await message.answer("Введите заголовок объявления (кратко, для канала):")


@router.message(SellerFlow.wait_title, F.text)
async def seller_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if not title or len(title) > MAX_TITLE:
        await message.answer(f"Заголовок: 1…{MAX_TITLE} символов.")
        return
    await state.update_data(title=title)
    await state.set_state(SellerFlow.wait_region)
    await message.answer("Регион:")


@router.message(SellerFlow.wait_region, F.text)
async def seller_region(message: Message, state: FSMContext) -> None:
    region = message.text.strip()
    if not region or len(region) > MAX_REGION:
        await message.answer(f"Регион: до {MAX_REGION} символов.")
        return
    await state.update_data(region=region)
    await state.set_state(SellerFlow.wait_rayon)
    await message.answer("Район / населённый пункт:")


@router.message(SellerFlow.wait_rayon, F.text)
async def seller_rayon(message: Message, state: FSMContext) -> None:
    rayon = message.text.strip()
    if not rayon or len(rayon) > MAX_RAYON:
        await message.answer(f"Район: до {MAX_RAYON} символов.")
        return
    await state.update_data(rayon=rayon)
    await state.set_state(SellerFlow.wait_comment)
    await message.answer("Описание / комментарий:")


@router.message(SellerFlow.wait_comment, F.text)
async def seller_comment(message: Message, state: FSMContext) -> None:
    comment = message.text.strip()
    if not comment or len(comment) > MAX_COMMENT:
        await message.answer(f"Описание: до {MAX_COMMENT} символов.")
        return
    await state.update_data(comment=comment)
    await state.set_state(SellerFlow.wait_ad_phone)
    data = await state.get_data()
    hint = data.get("reg_phone") or ""
    extra = f"\n(ваш номер при регистрации: {hint})" if hint else ""
    await message.answer(f"Телефон для связи по объявлению:{extra}")


@router.message(SellerFlow.wait_ad_phone, F.text)
async def seller_ad_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if len(phone) < 5 or len(phone) > MAX_PHONE:
        await message.answer("Укажите корректный номер или другой контакт для связи.")
        return
    await state.update_data(ad_phone=phone)
    await state.set_state(SellerFlow.wait_confirm)
    data = await state.get_data()
    summary = build_summary_for_seller(
        data["title"],
        data["region"],
        data["rayon"],
        data["comment"],
        phone,
    )
    photos_n = len(data.get("photos", []))
    vid = "да" if data.get("video") else "нет"
    await message.answer(
        summary + f"\n\nФото: {photos_n}, видео: {vid}",
        reply_markup=confirm_ad_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(SellerFlow.wait_confirm, F.data == "ad:cancel")
async def seller_cancel_ad(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.answer("Отменено")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cq.message.answer("Объявление не сохранено. Нажмите /start, чтобы начать снова.")


@router.callback_query(SellerFlow.wait_confirm, F.data == "ad:confirm")
async def seller_confirm_ad(cq: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    uid = cq.from_user.id
    window_start = time.time() - 3600
    recent = await db.count_recent_ads(uid, window_start)
    if recent >= settings.max_ads_per_hour:
        await cq.answer(
            "Слишком много объявлений за последний час. Попробуйте позже.",
            show_alert=True,
        )
        return

    data = await state.get_data()
    photos: list[str] = list(data.get("photos", []))
    if len(photos) < 1:
        await cq.answer("Нет фото — начните заново с /start.", show_alert=True)
        return

    media_items: list[MediaItem] = [
        MediaItem(kind="photo", file_id=fid, position=i) for i, fid in enumerate(photos)
    ]
    video = data.get("video")
    if video:
        media_items.append(MediaItem(kind="video", file_id=video, position=len(media_items)))

    ad_id = await db.create_ad(
        uid,
        data["title"],
        data["region"],
        data["rayon"],
        data["comment"],
        data["ad_phone"],
        media_items,
    )
    await state.clear()
    await cq.answer("Отправлено на модерацию")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cq.message.answer("Объявление принято модератором на проверку.")

    ad = await db.get_ad(ad_id)
    if not ad:
        return

    media = await db.get_ad_media(ad_id)
    from keyboards import admin_moderate_keyboard

    kb = admin_moderate_keyboard(ad_id)
    prefix = f"🛂 Модерация · #{ad_id}"
    for aid in settings.admin_ids:
        await send_ad_media(
            bot,
            aid,
            ad,
            media,
            reply_markup=kb,
            caption_prefix=prefix,
        )
