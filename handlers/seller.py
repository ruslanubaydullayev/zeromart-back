"""Seller flow: menu, photos (1–3) + video, text fields, confirm."""

from __future__ import annotations

import re
import time

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from database import Database, MediaItem
from formatting import build_summary_for_seller
from keyboards import (
    NEXT_STEP_TEXT,
    SUBMIT_AD_TEXT,
    confirm_ad_keyboard,
    contact_keyboard,
    main_menu_keyboard,
    media_next_reply_keyboard,
    remove_keyboard,
)
from posting import send_ad_media
from states import SellerFlow

router = Router(name="seller")

MIN_TITLE_LEN = 3
MAX_TITLE = 120
MIN_REGION_LEN = 3
MAX_REGION = 50
MIN_RAYON_LEN = 3
MAX_RAYON = 50
MIN_COMMENT_LEN = 4  # «более 4 символов»
MAX_COMMENT = 1500
# Телефон в объявлении: только +998 и 9 цифр (пример +998901234567)
AD_PHONE_UZ = re.compile(r"^\+998[0-9]{9}$")
MAX_LISTING_PHOTOS = 3

LISTING_MEDIA_INTRO = (
    "Сначала отправьте <b>от 1 до 3 фото</b> товара. После каждого фото появится кнопка "
    f"«{NEXT_STEP_TEXT}» под полем ввода (можно добавить ещё фото или нажать её, если фото готовы). "
    f"Затем пришлите <b>одно видео</b> и снова нажмите «{NEXT_STEP_TEXT}», чтобы перейти к тексту объявления."
)


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
    await state.update_data(listing_photos=[], listing_video_id=None)
    await state.set_state(SellerFlow.wait_media_photos)
    await message.answer(
        LISTING_MEDIA_INTRO,
        reply_markup=remove_keyboard(),
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
        "Спасибо, номер сохранён. Клавиатура «Поделиться телефоном» больше не нужна.\n"
        "В меню: <b>Разместить объявление</b> и <b>Мои объявления</b>.",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_phone)
async def seller_phone_required(message: Message) -> None:
    await message.answer(
        "Нужен номер из Telegram — нажмите «Поделиться телефоном».",
        reply_markup=contact_keyboard(),
    )


@router.message(SellerFlow.wait_media_photos, F.photo)
async def seller_listing_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = list(data.get("listing_photos") or [])
    if len(photos) >= MAX_LISTING_PHOTOS:
        await message.answer(
            f"Уже {MAX_LISTING_PHOTOS} фото. Нажмите «{NEXT_STEP_TEXT}», чтобы перейти к видео.",
            reply_markup=media_next_reply_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(listing_photos=photos)
    n = len(photos)
    await message.answer(
        f"Фото {n}/{MAX_LISTING_PHOTOS}. Можно добавить ещё или нажать «{NEXT_STEP_TEXT}».",
        reply_markup=media_next_reply_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_media_photos, F.text == NEXT_STEP_TEXT)
async def seller_photos_next(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = list(data.get("listing_photos") or [])
    if len(photos) < 1:
        await message.answer("Сначала отправьте хотя бы одно фото.")
        return
    await state.set_state(SellerFlow.wait_media_video)
    await message.answer(
        "Теперь отправьте <b>одно видео</b> товара. После загрузки появится «Дальше».",
        reply_markup=remove_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_media_photos, F.video)
async def seller_video_wrong_phase(message: Message) -> None:
    await message.answer(
        "Сначала закончите с фото (1–3 шт.) и нажмите «Дальше», затем отправьте видео.",
    )


@router.message(SellerFlow.wait_media_photos)
async def seller_photos_need_media(message: Message) -> None:
    await message.answer(
        "Пришлите до 3 фото или нажмите «Дальше», чтобы перейти к видео (нужно минимум 1 фото).",
        reply_markup=media_next_reply_keyboard(),
    )


@router.message(SellerFlow.wait_media_video, F.video)
async def seller_listing_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("listing_video_id"):
        await message.answer(
            "Видео уже получено. Нажмите «Дальше», чтобы продолжить.",
            reply_markup=media_next_reply_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(listing_video_id=message.video.file_id)
    await message.answer(
        f"Видео получено. Нажмите «{NEXT_STEP_TEXT}», чтобы перейти к тексту объявления.",
        reply_markup=media_next_reply_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_media_video, F.text == NEXT_STEP_TEXT)
async def seller_video_next(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("listing_video_id"):
        await message.answer("Сначала отправьте одно видео.")
        return
    await state.set_state(SellerFlow.wait_title)
    await message.answer(
        "Введите заголовок объявления (кратко, для канала):",
        reply_markup=remove_keyboard(),
    )


@router.message(SellerFlow.wait_media_video, F.photo)
async def seller_photo_wrong_phase_video(message: Message) -> None:
    await message.answer("Сейчас нужно только одно видео.")


@router.message(SellerFlow.wait_media_video)
async def seller_video_need_file(message: Message) -> None:
    await message.answer(
        "Пришлите одно видеофайл или нажмите «Дальше», если видео уже отправлено.",
        reply_markup=media_next_reply_keyboard(),
    )


@router.message(SellerFlow.wait_title, F.text)
async def seller_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if title == NEXT_STEP_TEXT:
        await message.answer("Введите заголовок текстом, а не кнопкой «Дальше».")
        return
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
        await message.answer("Комментарий должен содержать более 3 символов.")
        return
    if len(comment) > MAX_COMMENT:
        await message.answer(f"Комментарий: не более {MAX_COMMENT} символов.")
        return
    await state.update_data(comment=comment)
    await state.set_state(SellerFlow.wait_ad_phone)
    hint = await db.get_user_phone(message.from_user.id) or ""
    extra = f"\n(ваш номер при регистрации: {hint})" if hint else ""
    await message.answer(
        f"Телефон для связи по объявлению (строго <code>+998901234567</code> — плюс, 998 и 9 цифр):{extra}",
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_ad_phone, F.text)
async def seller_ad_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip().replace(" ", "")
    if not AD_PHONE_UZ.fullmatch(phone):
        await message.answer(
            "Номер только в формате <code>+998901234567</code>: плюс, 998, затем 9 цифр без пробелов.",
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(ad_phone=phone)
    await state.set_state(SellerFlow.wait_confirm)
    data = await state.get_data()
    n_photos = len(data.get("listing_photos") or [])
    summary = build_summary_for_seller(
        data["title"],
        data["region"],
        data["rayon"],
        data["comment"],
        phone,
    )
    await message.answer(
        summary + f"\n\nМедиа: {n_photos} фото, 1 видео",
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
            "Объявление не сохранено. Используйте меню ниже.",
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
    photos: list[str] = list(data.get("listing_photos") or [])
    video_fid = data.get("listing_video_id")
    if len(photos) < 1 or not video_fid:
        await cq.answer("Нужны хотя бы одно фото и видео — начните заново.", show_alert=True)
        return

    media_items = [
        MediaItem(kind="photo", file_id=fid, position=i) for i, fid in enumerate(photos)
    ]
    media_items.append(
        MediaItem(kind="video", file_id=video_fid, position=len(photos)),
    )

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
