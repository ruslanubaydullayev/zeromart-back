"""Seller flow: menu, photos (1–3) + video, text fields, confirm."""

from __future__ import annotations

import html
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
    use_registered_phone_keyboard,
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


def normalize_phone_to_ad_uz(raw: str) -> str | None:
    """Номер из Telegram/контакта часто без «+» — приводим к +998XXXXXXXXX."""
    s = raw.strip().replace(" ", "").replace("-", "")
    if not s:
        return None
    if AD_PHONE_UZ.fullmatch(s):
        return s
    if len(s) == 12 and s.startswith("998") and s.isdigit():
        return "+" + s
    if len(s) == 9 and s.isdigit():
        return "+998" + s
    return None


async def _complete_ad_phone_step(message: Message, state: FSMContext, phone: str) -> None:
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

LISTING_MEDIA_INTRO = (
    "Нужны <b>от 1 до 3 фото</b> и <b>одно видео</b> — <b>в любом порядке</b> (сначала видео или сначала фото — неважно). "
    f"Под полем ввода — «{NEXT_STEP_TEXT}». Когда и фото, и видео уже отправлены, нажмите «{NEXT_STEP_TEXT}», "
    "чтобы перейти к тексту объявления."
)


def _listing_media_complete(data: dict) -> bool:
    photos: list = list(data.get("listing_photos") or [])
    return len(photos) >= 1 and bool(data.get("listing_video_id"))


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
    await state.set_state(SellerFlow.wait_media)
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


@router.message(SellerFlow.wait_media, F.photo)
async def seller_listing_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = list(data.get("listing_photos") or [])
    if len(photos) >= MAX_LISTING_PHOTOS:
        await message.answer(
            f"Уже {MAX_LISTING_PHOTOS} фото. Нажмите «{NEXT_STEP_TEXT}», если есть и видео.",
            reply_markup=media_next_reply_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(listing_photos=photos)
    data = await state.get_data()
    n = len(photos)
    has_video = bool(data.get("listing_video_id"))
    if _listing_media_complete(data):
        text = (
            f"Фото {n}/{MAX_LISTING_PHOTOS}. Всё готово (есть фото и видео) — нажмите «{NEXT_STEP_TEXT}»."
        )
    elif has_video:
        text = f"Фото {n}/{MAX_LISTING_PHOTOS}. Можно добавить ещё фото или нажать «{NEXT_STEP_TEXT}»."
    else:
        text = (
            f"Фото {n}/{MAX_LISTING_PHOTOS}. Отправьте ещё <b>одно видео</b>, "
            f"потом «{NEXT_STEP_TEXT}»."
        )
    await message.answer(
        text,
        reply_markup=media_next_reply_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_media, F.video)
async def seller_listing_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("listing_video_id"):
        await message.answer(
            "Видео уже получено. Можно добавить фото (до 3) или нажать «Дальше», если всё готово.",
            reply_markup=media_next_reply_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(listing_video_id=message.video.file_id)
    data = await state.get_data()
    n = len(data.get("listing_photos") or [])
    if _listing_media_complete(data):
        text = f"Видео получено. Всё готово — нажмите «{NEXT_STEP_TEXT}»."
    elif n >= 1:
        text = (
            f"Видео получено. Фото: {n}/{MAX_LISTING_PHOTOS}. "
            f"Можно добавить ещё фото или нажать «{NEXT_STEP_TEXT}»."
        )
    else:
        text = (
            "Видео получено. Теперь отправьте <b>хотя бы одно фото</b>, "
            f"затем «{NEXT_STEP_TEXT}»."
        )
    await message.answer(
        text,
        reply_markup=media_next_reply_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_media, F.text == NEXT_STEP_TEXT)
async def seller_media_next(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = list(data.get("listing_photos") or [])
    if len(photos) < 1:
        await message.answer("Нужно хотя бы одно фото.")
        return
    if not data.get("listing_video_id"):
        await message.answer("Нужно одно видео.")
        return
    await state.set_state(SellerFlow.wait_title)
    await message.answer(
        "Введите заголовок объявления (кратко, для канала):",
        reply_markup=remove_keyboard(),
    )


@router.message(SellerFlow.wait_media)
async def seller_media_need_files(message: Message) -> None:
    await message.answer(
        "Пришлите фото (до 3) и одно видео — в любом порядке. "
        f"Когда оба типа файлов есть — «{NEXT_STEP_TEXT}».",
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
    extra = (
        f"\n(ваш номер при регистрации: <code>{html.escape(hint)}</code>)"
        if hint
        else ""
    )
    reg_kb = use_registered_phone_keyboard() if hint else None
    await message.answer(
        f"Телефон для связи по объявлению (формат <code>+998901234567</code>):{extra}\n\n"
        "Можно ввести вручную или нажать кнопку ниже.",
        reply_markup=reg_kb,
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(SellerFlow.wait_ad_phone, F.data == "ad_phone:reg")
async def use_registered_phone_cb(cq: CallbackQuery, state: FSMContext, db: Database) -> None:
    raw = await db.get_user_phone(cq.from_user.id)
    if not raw:
        await cq.answer("Номер регистрации не найден.", show_alert=True)
        return
    phone = normalize_phone_to_ad_uz(raw)
    if not phone:
        await cq.answer(
            "Не удалось привести номер из Telegram к виду +998… Введите номер вручную.",
            show_alert=True,
        )
        return
    if not AD_PHONE_UZ.fullmatch(phone):
        await cq.answer("Номер не подходит под формат +998…. Введите вручную.", show_alert=True)
        return
    await cq.answer("Подставлен номер из регистрации")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _complete_ad_phone_step(cq.message, state, phone)


@router.message(SellerFlow.wait_ad_phone, F.text)
async def seller_ad_phone(message: Message, state: FSMContext, db: Database) -> None:
    phone = message.text.strip().replace(" ", "")
    phone = normalize_phone_to_ad_uz(phone) or phone
    if not AD_PHONE_UZ.fullmatch(phone):
        reg_kb = (
            use_registered_phone_keyboard()
            if await db.get_user_phone(message.from_user.id)
            else None
        )
        await message.answer(
            "Номер только в формате <code>+998901234567</code>: плюс, 998, затем 9 цифр без пробелов.",
            reply_markup=reg_kb,
            parse_mode=ParseMode.HTML,
        )
        return
    await _complete_ad_phone_step(message, state, phone)


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
