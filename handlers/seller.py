"""Seller flow: menu, photos (1–3) + video, text fields, confirm."""

from __future__ import annotations

import html
import re
import time

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from database import Database, MediaItem
from formatting import build_summary_for_seller
from keyboards import (
    NEXT_STEP_TEXT,
    REG_PHONE_REPLY_TEXT,
    SUBMIT_AD_TEXT,
    WIZARD_BACK_TEXT,
    WIZARD_HOME_TEXT,
    confirm_ad_keyboard,
    contact_keyboard,
    main_menu_keyboard,
    remove_keyboard,
    wizard_media_reply_keyboard,
    wizard_nav_reply_keyboard,
    wizard_phone_reply_keyboard,
)
from posting import send_ad_media
from states import SellerFlow
from wizard_ui import go_wizard_home, wizard_delete_prompt_only, wizard_replace_prompt

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

TITLE_PROMPT = "Введите заголовок объявления (кратко, для канала):"
REGION_PROMPT = "Регион:"
RAYON_PROMPT = "Район / населённый пункт:"
COMMENT_PROMPT = "Описание / комментарий:"

WIZARD_REPLY_STATES = (
    SellerFlow.wait_media,
    SellerFlow.wait_title,
    SellerFlow.wait_region,
    SellerFlow.wait_rayon,
    SellerFlow.wait_comment,
    SellerFlow.wait_ad_phone,
)


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


LISTING_MEDIA_INTRO = (
    "Нужны <b>от 1 до 3 фото</b> и <b>одно видео</b> — <b>в любом порядке</b>. "
    f"Под полем ввода — «{NEXT_STEP_TEXT}». Когда и фото, и видео уже отправлены, нажмите «{NEXT_STEP_TEXT}». "
    f"«{WIZARD_BACK_TEXT}» — выйти в меню, «{WIZARD_HOME_TEXT}» — в начало (меню)."
)


def _listing_media_complete(data: dict) -> bool:
    photos: list = list(data.get("listing_photos") or [])
    return len(photos) >= 1 and bool(data.get("listing_video_id"))


async def _phone_prompt_for_user(db: Database, uid: int) -> tuple[str, bool]:
    hint = await db.get_user_phone(uid) or ""
    extra = (
        f"\n(ваш номер при регистрации: <code>{html.escape(hint)}</code>)"
        if hint
        else ""
    )
    text = (
        f"Телефон для связи по объявлению (формат <code>+998901234567</code>):{extra}\n\n"
        "Можно ввести вручную или нажать кнопку «Номер из регистрации»."
    )
    return text, bool(hint)


async def _complete_ad_phone_step(
    message: Message,
    state: FSMContext,
    phone: str,
    *,
    delete_user_message_id: int | None = None,
) -> None:
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
    await wizard_replace_prompt(
        message,
        state,
        summary + f"\n\nМедиа: {n_photos} фото, 1 видео",
        reply_markup=confirm_ad_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=delete_user_message_id,
    )


async def handle_wizard_back(message: Message, state: FSMContext, db: Database) -> None:
    st = await state.get_state()
    del_uid = message.message_id
    if st == SellerFlow.wait_media.state:
        await go_wizard_home(
            message,
            state,
            delete_user_message_id=del_uid,
            answer_text="Создание объявления отменено. Меню:",
            reply_markup=main_menu_keyboard(),
        )
        return
    if st == SellerFlow.wait_title.state:
        await state.update_data(title=None)
        await state.set_state(SellerFlow.wait_media)
        await wizard_replace_prompt(
            message,
            state,
            LISTING_MEDIA_INTRO,
            reply_markup=wizard_media_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return
    if st == SellerFlow.wait_region.state:
        await state.update_data(region=None)
        await state.set_state(SellerFlow.wait_title)
        await wizard_replace_prompt(
            message,
            state,
            TITLE_PROMPT,
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return
    if st == SellerFlow.wait_rayon.state:
        await state.update_data(rayon=None)
        await state.set_state(SellerFlow.wait_region)
        await wizard_replace_prompt(
            message,
            state,
            REGION_PROMPT,
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return
    if st == SellerFlow.wait_comment.state:
        await state.update_data(comment=None)
        await state.set_state(SellerFlow.wait_rayon)
        await wizard_replace_prompt(
            message,
            state,
            RAYON_PROMPT,
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return
    if st == SellerFlow.wait_ad_phone.state:
        await state.update_data(ad_phone=None)
        await state.set_state(SellerFlow.wait_comment)
        await wizard_replace_prompt(
            message,
            state,
            COMMENT_PROMPT,
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return


async def handle_wizard_home(message: Message, state: FSMContext) -> None:
    await go_wizard_home(
        message,
        state,
        delete_user_message_id=message.message_id,
        answer_text="Начинаем сначала. Выберите действие в меню:",
        reply_markup=main_menu_keyboard(),
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
    await state.set_state(SellerFlow.wait_media)
    await wizard_replace_prompt(
        message,
        state,
        LISTING_MEDIA_INTRO,
        reply_markup=wizard_media_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(StateFilter(*WIZARD_REPLY_STATES), F.text == WIZARD_BACK_TEXT)
async def wizard_back_reply(message: Message, state: FSMContext, db: Database) -> None:
    await handle_wizard_back(message, state, db)


@router.message(StateFilter(*WIZARD_REPLY_STATES), F.text == WIZARD_HOME_TEXT)
async def wizard_home_reply(message: Message, state: FSMContext) -> None:
    await handle_wizard_home(message, state)


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
        await wizard_replace_prompt(
            message,
            state,
            f"Уже {MAX_LISTING_PHOTOS} фото. Нажмите «{NEXT_STEP_TEXT}», если есть и видео.",
            reply_markup=wizard_media_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=None,
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
    await wizard_replace_prompt(
        message,
        state,
        text,
        reply_markup=wizard_media_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=None,
    )


@router.message(SellerFlow.wait_media, F.video)
async def seller_listing_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("listing_video_id"):
        await wizard_replace_prompt(
            message,
            state,
            "Видео уже получено. Можно добавить фото (до 3) или нажать «Дальше», если всё готово.",
            reply_markup=wizard_media_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=None,
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
    await wizard_replace_prompt(
        message,
        state,
        text,
        reply_markup=wizard_media_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=None,
    )


@router.message(SellerFlow.wait_media, F.text == NEXT_STEP_TEXT)
async def seller_media_next(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = list(data.get("listing_photos") or [])
    if len(photos) < 1:
        await wizard_replace_prompt(
            message,
            state,
            "Нужно хотя бы одно фото.",
            reply_markup=wizard_media_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if not data.get("listing_video_id"):
        await wizard_replace_prompt(
            message,
            state,
            "Нужно одно видео.",
            reply_markup=wizard_media_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.set_state(SellerFlow.wait_title)
    await wizard_replace_prompt(
        message,
        state,
        TITLE_PROMPT,
        reply_markup=wizard_nav_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_media)
async def seller_media_need_files(message: Message, state: FSMContext) -> None:
    await wizard_replace_prompt(
        message,
        state,
        "Пришлите фото (до 3) и одно видео — в любом порядке. "
        f"Когда оба типа файлов есть — «{NEXT_STEP_TEXT}».",
        reply_markup=wizard_media_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_title, F.text)
async def seller_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if title == NEXT_STEP_TEXT:
        await wizard_replace_prompt(
            message,
            state,
            "Введите заголовок текстом, а не кнопкой «Дальше».",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(title) < MIN_TITLE_LEN:
        await wizard_replace_prompt(
            message,
            state,
            f"Заголовок должен содержать не менее {MIN_TITLE_LEN} символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(title) > MAX_TITLE:
        await wizard_replace_prompt(
            message,
            state,
            f"Заголовок не длиннее {MAX_TITLE} символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(title=title)
    await state.set_state(SellerFlow.wait_region)
    await wizard_replace_prompt(
        message,
        state,
        REGION_PROMPT,
        reply_markup=wizard_nav_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_region, F.text)
async def seller_region(message: Message, state: FSMContext) -> None:
    region = message.text.strip()
    if len(region) < MIN_REGION_LEN:
        await wizard_replace_prompt(
            message,
            state,
            f"Регион: укажите не менее {MIN_REGION_LEN} символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(region) > MAX_REGION:
        await wizard_replace_prompt(
            message,
            state,
            f"Регион: не более {MAX_REGION} символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(region=region)
    await state.set_state(SellerFlow.wait_rayon)
    await wizard_replace_prompt(
        message,
        state,
        RAYON_PROMPT,
        reply_markup=wizard_nav_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_rayon, F.text)
async def seller_rayon(message: Message, state: FSMContext) -> None:
    rayon = message.text.strip()
    if len(rayon) < MIN_RAYON_LEN:
        await wizard_replace_prompt(
            message,
            state,
            f"Район: укажите не менее {MIN_RAYON_LEN} символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(rayon) > MAX_RAYON:
        await wizard_replace_prompt(
            message,
            state,
            f"Район: не более {MAX_RAYON} символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(rayon=rayon)
    await state.set_state(SellerFlow.wait_comment)
    await wizard_replace_prompt(
        message,
        state,
        COMMENT_PROMPT,
        reply_markup=wizard_nav_reply_keyboard(),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_comment, F.text)
async def seller_comment(message: Message, state: FSMContext, db: Database) -> None:
    comment = message.text.strip()
    if len(comment) < MIN_COMMENT_LEN:
        await wizard_replace_prompt(
            message,
            state,
            "Комментарий должен содержать более 3 символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(comment) > MAX_COMMENT:
        await wizard_replace_prompt(
            message,
            state,
            f"Комментарий: не более {MAX_COMMENT} символов.",
            reply_markup=wizard_nav_reply_keyboard(),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(comment=comment)
    await state.set_state(SellerFlow.wait_ad_phone)
    text, with_reg = await _phone_prompt_for_user(db, message.from_user.id)
    await wizard_replace_prompt(
        message,
        state,
        text,
        reply_markup=wizard_phone_reply_keyboard(with_registered=with_reg),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_ad_phone, F.text == REG_PHONE_REPLY_TEXT)
async def use_registered_phone_msg(message: Message, state: FSMContext, db: Database) -> None:
    raw = await db.get_user_phone(message.from_user.id)
    if not raw:
        await wizard_replace_prompt(
            message,
            state,
            "Номер регистрации не найден. Введите номер вручную.",
            reply_markup=wizard_phone_reply_keyboard(with_registered=False),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    phone = normalize_phone_to_ad_uz(raw)
    if not phone or not AD_PHONE_UZ.fullmatch(phone):
        await wizard_replace_prompt(
            message,
            state,
            "Не удалось привести номер из Telegram к виду +998…. Введите номер вручную.",
            reply_markup=wizard_phone_reply_keyboard(with_registered=True),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await _complete_ad_phone_step(
        message, state, phone, delete_user_message_id=message.message_id
    )


@router.message(SellerFlow.wait_ad_phone, F.text)
async def seller_ad_phone(message: Message, state: FSMContext, db: Database) -> None:
    phone = message.text.strip().replace(" ", "")
    phone = normalize_phone_to_ad_uz(phone) or phone
    if not AD_PHONE_UZ.fullmatch(phone):
        has_reg = bool(await db.get_user_phone(message.from_user.id))
        await wizard_replace_prompt(
            message,
            state,
            "Номер только в формате <code>+998901234567</code>: плюс, 998, затем 9 цифр без пробелов.",
            reply_markup=wizard_phone_reply_keyboard(with_registered=has_reg),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await _complete_ad_phone_step(
        message, state, phone, delete_user_message_id=message.message_id
    )


@router.callback_query(SellerFlow.wait_confirm, F.data == "wiz:back")
async def wizard_back_confirm(cq: CallbackQuery, state: FSMContext, db: Database) -> None:
    await cq.answer()
    await state.update_data(ad_phone=None)
    await state.set_state(SellerFlow.wait_ad_phone)
    text, with_reg = await _phone_prompt_for_user(db, cq.from_user.id)
    await wizard_replace_prompt(
        cq.message,
        state,
        text,
        reply_markup=wizard_phone_reply_keyboard(with_registered=with_reg),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=None,
    )


@router.callback_query(SellerFlow.wait_confirm, F.data == "wiz:home")
async def wizard_home_confirm(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await go_wizard_home(
        cq.message,
        state,
        delete_user_message_id=None,
        answer_text="Начинаем сначала. Выберите действие в меню:",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(SellerFlow.wait_confirm, F.data == "ad:cancel")
async def seller_cancel_ad(cq: CallbackQuery, state: FSMContext, db: Database) -> None:
    uid = cq.from_user.id
    bot = cq.message.bot
    chat_id = cq.message.chat.id
    await cq.answer("Отменено")
    await wizard_delete_prompt_only(cq.message, state)
    await state.clear()
    if uid not in settings.admin_ids and await db.user_has_phone(uid):
        await bot.send_message(
            chat_id,
            "Объявление не сохранено. Используйте меню ниже.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await bot.send_message(chat_id, "Объявление не сохранено. Нажмите /start.")


@router.callback_query(SellerFlow.wait_confirm, F.data == "ad:confirm")
async def seller_confirm_ad(cq: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    uid = cq.from_user.id
    chat_id = cq.message.chat.id
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
    await cq.answer("Отправлено на модерацию")
    await wizard_delete_prompt_only(cq.message, state)
    await state.clear()
    if uid not in settings.admin_ids and await db.user_has_phone(uid):
        await bot.send_message(
            chat_id,
            "Объявление принято модератором на проверку.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await bot.send_message(chat_id, "Объявление принято модератором на проверку.")

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
