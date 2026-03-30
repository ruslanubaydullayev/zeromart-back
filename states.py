"""FSM states for seller and admin flows."""

from aiogram.fsm.state import State, StatesGroup


class SellerFlow(StatesGroup):
    wait_phone = State()
    wait_media_photos = State()
    wait_media_video = State()
    wait_title = State()
    wait_region = State()
    wait_rayon = State()
    wait_comment = State()
    wait_ad_phone = State()
    wait_confirm = State()


class AdminFlow(StatesGroup):
    wait_reject_reason = State()
