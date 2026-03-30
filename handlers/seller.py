"""Seller flow: menu, required photo + video, text fields, confirm."""

from __future__ import annotations

import time

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from database import Database, MediaItem
from formatting import build_summary_for_seller
from keyboards import (
    SUBMIT_AD_TEXT,
    confirm_ad_keyboard,
    contact_keyboard,
    listing_media_next_keyboard,
    main_menu_keyboard,
    remove_keyboard,
)
from posting import send_ad_media
from states import SellerFlow

router = Router(name="seller")

MIN_TITLE_LEN = 3
MAX_TITLE = 120
MIN_REGION_LEN = 2
MAX_REGION = 80
MIN_RAYON_LEN = 2
MAX_RAYON = 80
MIN_COMMENT_LEN = 4  # «более 3 символов»
MAX_COMMENT = 1500
MIN_PHONE_LEN = 5
MAX_PHONE = 40

LISTING_MEDIA_INTRO = (
    "Отправьте <b>одно фото</b> и <b>одно видео</b> товара — оба обязательны. "
    "Порядок любой. После каждого загруженного файла нажимайте «Дальше». "
    "Когда оба файла будут на месте, снова нажмите «Дальше», чтобы перейти к тексту объявления."
)


def _both_media_ready(data: dict) -> bool:
    return bool(data.get("listing_photo_id")) and bool(data.get("listing_video_id"))


@router.message(F.text == SUBMIT_AD_TEXT)
async def submit_ad_from_menu(message: Message, state: FSMContext, db: Database) -> None:
    if message.from_user.id in settings.admin_ids:
        await message.answer("Это меню для продавцов — у вас роль модератора.")
        return
    if not await db.user_has_phone(message.from_user.id):
        await message.answer(
            "Сначала нажмите /start и поделитесь номером телефона.",
            reply_markup=remove_keyboard(),
        )
        return
    await state.update_data(listing_photo_id=None, listing_video_id=None)
    await state.set_state(SellerFlow.wait_media)
    await message.answer(
        LISTING_MEDIA_INTRO,
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


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
    await state.clear()
    await message.answer(
        "Спасибо, номер сохранён. Вы авторизованы — номер больше не запрашиваем.\n"
        "Чтобы подать объявление, нажмите <b>Подать объявление</b> в меню.",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_phone)
async def seller_phone_required(message: Message) -> None:
    await message.answer(
        "Нужен номер из Telegram — нажмите «Поделиться телефоном».",
        reply_markup=contact_keyboard(),
    )


@router.callback_query(SellerFlow.wait_media, F.data == "listing_media:done")
async def listing_media_done(cq: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("listing_photo_id") and not data.get("listing_video_id"):
        await cq.answer("Сначала отправьте фото и видео.", show_alert=True)
        return
    if not data.get("listing_photo_id"):
        await cq.answer("Сначала отправьте одно фото.", show_alert=True)
        return
    if not data.get("listing_video_id"):
        await cq.answer("Сначала отправьте одно видео.", show_alert=True)
        return
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(SellerFlow.wait_title)
    await cq.message.answer("Введите заголовок объявления (кратко, для канала):")


@router.message(SellerFlow.wait_media, F.photo)
async def seller_listing_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("listing_photo_id"):
        await message.answer(
            "Фото уже получено. Пришлите <b>одно видео</b> или нажмите «Дальше», если оно уже отправлено.",
            reply_markup=listing_media_next_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(listing_photo_id=message.photo[-1].file_id)
    await message.answer(
        "Фото получено. Нажмите «Дальше».",
        reply_markup=listing_media_next_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_media, F.video)
async def seller_listing_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("listing_video_id"):
        await message.answer(
            "Видео уже получено. Пришлите <b>одно фото</b> или нажмите «Дальше», если оно уже отправлено.",
            reply_markup=listing_media_next_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(listing_video_id=message.video.file_id)
    await message.answer(
        "Видео получено. Нажмите «Дальше».",
        reply_markup=listing_media_next_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_media)
async def seller_media_need_files(message: Message) -> None:
    await message.answer(
        "Нужны медиафайлы: одно <b>фото</b> и одно <b>видео</b> (не текст и не «кружок»).",
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_title, F.text)
async def seller_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < MIN_TITLE_LEN:
        await message.answer(
            f"Заголовок должен содержать не менее {MIN_TITLE_LEN} символов."
        )
        return
    if len(title) > MAX_TITLE:
        await message.answer(f"Заголовок не длиннее {MAX_TITLE} символов.")
        return
    await state.update_data(title=title)
    await state.set_state(SellerFlow.wait_region)
    await message.answer("Регион:")


@router.message(SellerFlow.wait_region, F.text)
async def seller_region(message: Message, state: FSMContext) -> None:
    region = message.text.strip()
    if len(region) < MIN_REGION_LEN:
        await message.answer(
            f"Регион: укажите не менее {MIN_REGION_LEN} символов."
        )
        return
    if len(region) > MAX_REGION:
        await message.answer(f"Регион: не более {MAX_REGION} символов.")
        return
    await state.update_data(region=region)
    await state.set_state(SellerFlow.wait_rayon)
    await message.answer("Район / населённый пункт:")


@router.message(SellerFlow.wait_rayon, F.text)
async def seller_rayon(message: Message, state: FSMContext) -> None:
    rayon = message.text.strip()
    if len(rayon) < MIN_RAYON_LEN:
        await message.answer(
            f"Район: укажите не менее {MIN_RAYON_LEN} символов."
        )
        return
    if len(rayon) > MAX_RAYON:
        await message.answer(f"Район: не более {MAX_RAYON} символов.")
        return
    await state.update_data(rayon=rayon)
    await state.set_state(SellerFlow.wait_comment)
    await message.answer("Описание / комментарий:")


@router.message(SellerFlow.wait_comment, F.text)
async def seller_comment(message: Message, state: FSMContext, db: Database) -> None:
    comment = message.text.strip()
    if len(comment) < MIN_COMMENT_LEN:
        await message.answer("Комментарий должен содержать более 4 символов.")
        return
    if len(comment) > MAX_COMMENT:
        await message.answer(f"Комментарий: не более {MAX_COMMENT} символов.")
        return
    await state.update_data(comment=comment)
    await state.set_state(SellerFlow.wait_ad_phone)
    hint = await db.get_user_phone(message.from_user.id) or ""
    extra = f"\n(ваш номер при регистрации: {hint})" if hint else ""
    await message.answer(f"Телефон для связи по объявлению:{extra}")


@router.message(SellerFlow.wait_ad_phone, F.text)
async def seller_ad_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if len(phone) < MIN_PHONE_LEN:
        await message.answer(
            f"Телефон для связи: укажите не менее {MIN_PHONE_LEN} символов."
        )
        return
    if len(phone) > MAX_PHONE:
        await message.answer(f"Телефон: не более {MAX_PHONE} символов.")
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
    await message.answer(
        summary + "\n\nМедиа: 1 фото, 1 видео",
        reply_markup=confirm_ad_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(SellerFlow.wait_confirm, F.data == "ad:cancel")
async def seller_cancel_ad(cq: CallbackQuery, state: FSMContext, db: Database) -> None:
    uid = cq.from_user.id
    await state.clear()
    await cq.answer("Отменено")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    if uid not in settings.admin_ids and await db.user_has_phone(uid):
        await cq.message.answer(
            "Объявление не сохранено. Можете снова нажать «Подать объявление».",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await cq.message.answer("Объявление не сохранено. Нажмите /start.")


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
    photo_fid = data.get("listing_photo_id")
    video_fid = data.get("listing_video_id")
    if not photo_fid or not video_fid:
        await cq.answer("Нужны фото и видео — начните заново.", show_alert=True)
        return

    media_items = [
        MediaItem(kind="photo", file_id=photo_fid, position=0),
        MediaItem(kind="video", file_id=video_fid, position=1),
    ]

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
    if uid not in settings.admin_ids and await db.user_has_phone(uid):
        await cq.message.answer(
            "Объявление принято модератором на проверку.",
            reply_markup=main_menu_keyboard(),
        )
    else:
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
