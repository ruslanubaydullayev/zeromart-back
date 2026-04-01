"""Seller flow: menu, photos (1–3) + video, text fields, confirm."""

from __future__ import annotations

import html
import re
import time

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, InputMediaVideo, Message

from config import settings
from database import Database, MediaItem
from formatting import build_summary_for_seller
from keyboards import (
    confirm_ad_keyboard,
    contact_keyboard,
    category_reply_keyboard,
    main_menu_keyboard,
    remove_keyboard,
    rayon_tashkent_reply_keyboard,
    region_reply_keyboard,
    wizard_media_reply_keyboard,
    wizard_nav_reply_keyboard,
    wizard_phone_reply_keyboard,
)
from language import (
    REGION_TASHKENT,
    all_category_button_texts,
    all_district_button_texts,
    all_variant_texts,
    category_label,
    category_slug_from_button_text,
    district_canonical,
    district_slug_from_button_text,
    normalize_locale,
    tr,
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

WIZARD_REPLY_STATES = (
    SellerFlow.wait_media,
    SellerFlow.wait_title,
    SellerFlow.wait_category,
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


def _lang_from_data(data: dict) -> str:
    return normalize_locale(data.get("lang"))


def _listing_media_complete(data: dict) -> bool:
    photos: list = list(data.get("listing_photos") or [])
    return len(photos) >= 1


async def _phone_prompt_for_user(db: Database, uid: int) -> tuple[str, bool]:
    hint = await db.get_user_phone(uid) or ""
    lang = normalize_locale(await db.get_user_lang(uid))
    extra = tr(lang, "phone_reg_hint", phone=html.escape(hint)) if hint else ""
    text = tr(lang, "phone_prompt", hint=extra)
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
    lang = _lang_from_data(data)
    n_photos = len(data.get("listing_photos") or [])
    has_video = bool(data.get("listing_video_id"))
    video_part = ", 1 видео" if has_video else ""
    summary = build_summary_for_seller(
        lang,
        data["category"],
        data["title"],
        data["region"],
        data["rayon"],
        data["comment"],
        phone,
    )
    preview_caption = summary + f"\n\n{tr(lang, 'summary_media', photos=n_photos, video_part=video_part)}"
    photos: list[str] = list(data.get("listing_photos") or [])
    video_fid = data.get("listing_video_id")
    if photos or video_fid:
        media_bundle: list[InputMediaPhoto | InputMediaVideo] = []
        for idx, fid in enumerate(photos):
            media_bundle.append(
                InputMediaPhoto(
                    media=fid,
                    caption=preview_caption if idx == 0 else None,
                    parse_mode=ParseMode.HTML if idx == 0 else None,
                )
            )
        if video_fid:
            media_bundle.append(
                InputMediaVideo(
                    media=video_fid,
                    caption=preview_caption if not photos else None,
                    parse_mode=ParseMode.HTML if not photos else None,
                )
            )
        await message.answer_media_group(media=media_bundle)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "confirm_prompt_after_preview"),
        reply_markup=confirm_ad_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=delete_user_message_id,
    )


async def handle_wizard_back(message: Message, state: FSMContext, db: Database) -> None:
    st = await state.get_state()
    del_uid = message.message_id
    lang = normalize_locale(await db.get_user_lang(message.from_user.id))
    if st == SellerFlow.wait_media.state:
        await go_wizard_home(
            message,
            state,
            delete_user_message_id=del_uid,
            answer_text=tr(lang, "wizard_cancel_listing"),
            reply_markup=main_menu_keyboard(lang),
        )
        return
    if st == SellerFlow.wait_title.state:
        await state.update_data(title=None)
        await state.set_state(SellerFlow.wait_media)
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "listing_media_intro", next=tr(lang, "next"), back=tr(lang, "back"), home=tr(lang, "home")),
            reply_markup=wizard_media_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return
    if st == SellerFlow.wait_category.state:
        await state.update_data(category=None)
        await state.set_state(SellerFlow.wait_title)
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "title_prompt"),
            reply_markup=wizard_nav_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return
    if st == SellerFlow.wait_region.state:
        await state.update_data(region=None)
        await state.set_state(SellerFlow.wait_category)
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "category_prompt"),
            reply_markup=category_reply_keyboard(lang),
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
            tr(lang, "region_prompt"),
            reply_markup=region_reply_keyboard(lang),
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
            tr(lang, "rayon_prompt"),
            reply_markup=rayon_tashkent_reply_keyboard(lang),
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
            tr(lang, "comment_prompt"),
            reply_markup=wizard_nav_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=del_uid,
        )
        return


async def handle_wizard_home(message: Message, state: FSMContext) -> None:
    # language is not available here without db; caller should prefer go_wizard_home directly.
    await go_wizard_home(message, state, delete_user_message_id=message.message_id)

@router.message(F.text.in_(all_variant_texts("menu_submit")))
async def submit_ad_from_menu(message: Message, state: FSMContext, db: Database) -> None:
    lang = normalize_locale(await db.get_user_lang(message.from_user.id))
    if message.from_user.id in settings.admin_ids:
        await message.answer(tr(lang, "submit_blocked_admin"))
        return
    if not await db.user_has_phone(message.from_user.id):
        await message.answer(
            tr(lang, "submit_need_start"),
            reply_markup=remove_keyboard(),
        )
        return
    await state.update_data(lang=lang, listing_photos=[], listing_video_id=None)
    await state.set_state(SellerFlow.wait_media)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "listing_media_intro", next=tr(lang, "next"), back=tr(lang, "back"), home=tr(lang, "home")),
        reply_markup=wizard_media_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(StateFilter(*WIZARD_REPLY_STATES), F.text.in_(all_variant_texts("back")))
async def wizard_back_reply(message: Message, state: FSMContext, db: Database) -> None:
    await handle_wizard_back(message, state, db)


@router.message(StateFilter(*WIZARD_REPLY_STATES), F.text.in_(all_variant_texts("home")))
async def wizard_home_reply(message: Message, state: FSMContext, db: Database) -> None:
    lang = normalize_locale(await db.get_user_lang(message.from_user.id))
    await go_wizard_home(
        message,
        state,
        delete_user_message_id=message.message_id,
        answer_text=tr(lang, "wizard_restart_menu"),
        reply_markup=main_menu_keyboard(lang),
    )


@router.message(SellerFlow.wait_phone, F.contact)
async def seller_phone(message: Message, state: FSMContext, db: Database) -> None:
    phone = message.contact.phone_number
    uid = message.from_user.id
    lang = normalize_locale(await db.get_user_lang(uid))
    await db.upsert_user(
        uid,
        phone=phone,
        lang=None,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
    )
    await state.clear()
    await message.answer(
        tr(
            lang,
            "thank_you_phone_saved",
            submit=tr(lang, "menu_submit"),
            my_ads=tr(lang, "menu_my_ads"),
        ),
        reply_markup=main_menu_keyboard(lang),
        parse_mode=ParseMode.HTML,
    )


@router.message(SellerFlow.wait_phone)
async def seller_phone_required(message: Message, db: Database) -> None:
    lang = normalize_locale(await db.get_user_lang(message.from_user.id))
    await message.answer(
        tr(lang, "phone_required_contact", share=tr(lang, "share_contact")),
        reply_markup=contact_keyboard(lang),
    )


@router.message(SellerFlow.wait_media, F.photo)
async def seller_listing_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    photos: list[str] = list(data.get("listing_photos") or [])
    if len(photos) >= MAX_LISTING_PHOTOS:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "photos_max", max=MAX_LISTING_PHOTOS, next=tr(lang, "next")),
            reply_markup=wizard_media_reply_keyboard(lang),
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
        text = tr(lang, "photo_ready", n=n, max=MAX_LISTING_PHOTOS, next=tr(lang, "next"))
    elif has_video:
        text = tr(lang, "photo_more_or_next", n=n, max=MAX_LISTING_PHOTOS, next=tr(lang, "next"))
    else:
        text = tr(lang, "photo_more_or_next", n=n, max=MAX_LISTING_PHOTOS, next=tr(lang, "next"))
    await wizard_replace_prompt(
        message,
        state,
        text,
        reply_markup=wizard_media_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=None,
    )


@router.message(SellerFlow.wait_media, F.video)
async def seller_listing_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    if data.get("listing_video_id"):
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "video_exists", max=MAX_LISTING_PHOTOS, next=tr(lang, "next")),
            reply_markup=wizard_media_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=None,
        )
        return
    await state.update_data(listing_video_id=message.video.file_id)
    data = await state.get_data()
    n = len(data.get("listing_photos") or [])
    if _listing_media_complete(data):
        text = tr(lang, "video_ready", next=tr(lang, "next"))
    elif n >= 1:
        text = tr(lang, "video_photo_progress", n=n, max=MAX_LISTING_PHOTOS, next=tr(lang, "next"))
    else:
        text = tr(lang, "video_need_photo", next=tr(lang, "next"))
    await wizard_replace_prompt(
        message,
        state,
        text,
        reply_markup=wizard_media_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=None,
    )


@router.message(SellerFlow.wait_media, F.text.in_(all_variant_texts("next")))
async def seller_media_next(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    photos: list[str] = list(data.get("listing_photos") or [])
    if len(photos) < 1:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "need_photo"),
            reply_markup=wizard_media_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.set_state(SellerFlow.wait_title)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "title_prompt"),
        reply_markup=wizard_nav_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_media)
async def seller_media_need_files(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "send_photos_video", max=MAX_LISTING_PHOTOS, next=tr(lang, "next")),
        reply_markup=wizard_media_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_title, F.text)
async def seller_title(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    title = message.text.strip()
    if len(title) < MIN_TITLE_LEN:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "title_err_min", min=MIN_TITLE_LEN),
            reply_markup=wizard_nav_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(title) > MAX_TITLE:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "title_err_max", max=MAX_TITLE),
            reply_markup=wizard_nav_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(title=title)
    await state.set_state(SellerFlow.wait_category)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "category_prompt"),
        reply_markup=category_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_category, F.text.in_(all_category_button_texts()))
async def seller_category(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    slug = category_slug_from_button_text(message.text or "")
    if not slug:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "category_prompt"),
            reply_markup=category_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(category=slug)
    await state.set_state(SellerFlow.wait_region)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "region_prompt"),
        reply_markup=region_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_category, F.text)
async def seller_category_other(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "category_prompt"),
        reply_markup=category_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_region, F.text)
async def seller_region(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    region_text = (message.text or "").strip()
    if region_text == tr(lang, "region_tashkent"):
        await state.update_data(region=REGION_TASHKENT)
        await state.set_state(SellerFlow.wait_rayon)
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "rayon_prompt"),
            reply_markup=rayon_tashkent_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return

    if len(region_text) < MIN_REGION_LEN:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "region_prompt"),
            reply_markup=region_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(region_text) > MAX_REGION:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "region_prompt"),
            reply_markup=region_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(region=region_text)
    await state.set_state(SellerFlow.wait_rayon)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "rayon_prompt"),
        reply_markup=wizard_nav_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_rayon, F.text)
async def seller_rayon(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    rayon_text = (message.text or "").strip()
    if (data.get("region") == REGION_TASHKENT) and (rayon_text in all_district_button_texts()):
        slug = district_slug_from_button_text(rayon_text)
        if slug:
            rayon_text = district_canonical(slug)

    if len(rayon_text) < MIN_RAYON_LEN:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "rayon_prompt"),
            reply_markup=rayon_tashkent_reply_keyboard(lang)
            if data.get("region") == REGION_TASHKENT
            else wizard_nav_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(rayon_text) > MAX_RAYON:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "rayon_prompt"),
            reply_markup=rayon_tashkent_reply_keyboard(lang)
            if data.get("region") == REGION_TASHKENT
            else wizard_nav_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await state.update_data(rayon=rayon_text)
    await state.set_state(SellerFlow.wait_comment)
    await wizard_replace_prompt(
        message,
        state,
        tr(lang, "comment_prompt"),
        reply_markup=wizard_nav_reply_keyboard(lang),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_comment, F.text)
async def seller_comment(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    comment = message.text.strip()
    if len(comment) < MIN_COMMENT_LEN:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "comment_err_short"),
            reply_markup=wizard_nav_reply_keyboard(lang),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    if len(comment) > MAX_COMMENT:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "comment_err_long", max=MAX_COMMENT),
            reply_markup=wizard_nav_reply_keyboard(lang),
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
        reply_markup=wizard_phone_reply_keyboard(lang, with_registered=with_reg),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=message.message_id,
    )


@router.message(SellerFlow.wait_ad_phone, F.text.in_(all_variant_texts("reg_phone")))
async def use_registered_phone_msg(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    raw = await db.get_user_phone(message.from_user.id)
    if not raw:
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "phone_err_not_found"),
            reply_markup=wizard_phone_reply_keyboard(lang, with_registered=False),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    phone = normalize_phone_to_ad_uz(raw)
    if not phone or not AD_PHONE_UZ.fullmatch(phone):
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "phone_err_normalize"),
            reply_markup=wizard_phone_reply_keyboard(lang, with_registered=True),
            parse_mode=ParseMode.HTML,
            delete_user_message_id=message.message_id,
        )
        return
    await _complete_ad_phone_step(
        message, state, phone, delete_user_message_id=message.message_id
    )


@router.message(SellerFlow.wait_ad_phone, F.text)
async def seller_ad_phone(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    lang = _lang_from_data(data)
    phone = message.text.strip().replace(" ", "")
    phone = normalize_phone_to_ad_uz(phone) or phone
    if not AD_PHONE_UZ.fullmatch(phone):
        has_reg = bool(await db.get_user_phone(message.from_user.id))
        await wizard_replace_prompt(
            message,
            state,
            tr(lang, "phone_err_format"),
            reply_markup=wizard_phone_reply_keyboard(lang, with_registered=has_reg),
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
    lang = normalize_locale(await db.get_user_lang(cq.from_user.id))
    await state.update_data(ad_phone=None)
    await state.set_state(SellerFlow.wait_ad_phone)
    text, with_reg = await _phone_prompt_for_user(db, cq.from_user.id)
    await wizard_replace_prompt(
        cq.message,
        state,
        text,
        reply_markup=wizard_phone_reply_keyboard(lang, with_registered=with_reg),
        parse_mode=ParseMode.HTML,
        delete_user_message_id=None,
    )


@router.callback_query(SellerFlow.wait_confirm, F.data == "wiz:home")
async def wizard_home_confirm(cq: CallbackQuery, state: FSMContext, db: Database) -> None:
    await cq.answer()
    lang = normalize_locale(await db.get_user_lang(cq.from_user.id))
    await go_wizard_home(
        cq.message,
        state,
        delete_user_message_id=None,
        answer_text=tr(lang, "wizard_restart_menu"),
        reply_markup=main_menu_keyboard(lang),
    )


@router.callback_query(SellerFlow.wait_confirm, F.data == "ad:cancel")
async def seller_cancel_ad(cq: CallbackQuery, state: FSMContext, db: Database) -> None:
    uid = cq.from_user.id
    lang = normalize_locale(await db.get_user_lang(uid))
    bot = cq.message.bot
    chat_id = cq.message.chat.id
    await cq.answer(tr(lang, "cancel_inline"))
    await wizard_delete_prompt_only(cq.message, state)
    await state.clear()
    if uid not in settings.admin_ids and await db.user_has_phone(uid):
        await bot.send_message(
            chat_id,
            tr(lang, "ad_not_saved_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
    else:
        await bot.send_message(chat_id, tr(lang, "ad_not_saved_start"))


@router.callback_query(SellerFlow.wait_confirm, F.data == "ad:confirm")
async def seller_confirm_ad(cq: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    uid = cq.from_user.id
    lang = normalize_locale(await db.get_user_lang(uid))
    chat_id = cq.message.chat.id
    window_start = time.time() - 3600
    recent = await db.count_recent_ads(uid, window_start)
    if recent >= settings.max_ads_per_hour:
        await cq.answer(
            tr(lang, "rate_limit"),
            show_alert=True,
        )
        return

    data = await state.get_data()
    photos: list[str] = list(data.get("listing_photos") or [])
    video_fid = data.get("listing_video_id")
    if len(photos) < 1:
        await cq.answer(tr(lang, "ad_incomplete_restart"), show_alert=True)
        return

    media_items = [
        MediaItem(kind="photo", file_id=fid, position=i) for i, fid in enumerate(photos)
    ]
    if video_fid:
        media_items.append(
            MediaItem(kind="video", file_id=video_fid, position=len(photos)),
        )

    ad_id = await db.create_ad(
        uid,
        data["category"],
        data["title"],
        data["region"],
        data["rayon"],
        data["comment"],
        data["ad_phone"],
        media_items,
    )
    await cq.answer(tr(lang, "ad_sent_moderation"))
    await wizard_delete_prompt_only(cq.message, state)
    await state.clear()
    if uid not in settings.admin_ids and await db.user_has_phone(uid):
        await bot.send_message(
            chat_id,
            tr(lang, "ad_accepted_check"),
            reply_markup=main_menu_keyboard(lang),
        )
    else:
        await bot.send_message(chat_id, tr(lang, "ad_accepted_check"))

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
