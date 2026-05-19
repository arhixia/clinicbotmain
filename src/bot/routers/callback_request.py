from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from src.bot.states.callback_states import CallbackStates
from src.services.amo_crm import AmoCRMService
from src.db.database import AsyncSessionLocal
from src.bot.routers.user_service import get_user_phone, save_phone

router = Router()
amo_service = AmoCRMService()


@router.callback_query(F.data == "callback_start")
async def process_callback_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = callback.from_user

    async with AsyncSessionLocal() as session:
        phone = await get_user_phone(session, user.id)

    if phone:
        amo_service.create_callback_lead(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            phone=phone,
        )
        await callback.message.answer(
            "✅ <b>Заявка принята!</b>\n\n"
            f"Перезвоним на номер <b>{phone}</b> в ближайшее время.\n"
            "Спасибо, что выбрали нас! 🙏"
        )
        return

    await state.set_state(CallbackStates.waiting_for_phone)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await callback.message.answer(
        "📞 <b>Обратный звонок</b>\n\n"
        "Поделитесь номером телефона и мы перезвоним в ближайшее время.",
        reply_markup=keyboard,
    )


@router.message(StateFilter(CallbackStates.waiting_for_phone), F.contact)
async def process_phone_contact(message: Message, state: FSMContext) -> None:
    await state.clear()
    phone = message.contact.phone_number
    user = message.from_user

    async with AsyncSessionLocal() as session:
        await save_phone(session, user.id, phone)
        await session.commit() 

    amo_service.create_callback_lead(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        phone=phone,
    )
    
    await message.answer(
        "✅ <b>Заявка принята!</b>\n\n"
        "Мы перезвоним вам в ближайшее время.\n"
        "Спасибо, что выбрали нас! 🙏",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(StateFilter(CallbackStates.waiting_for_phone), F.text == "❌ Отмена")
async def process_callback_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=ReplyKeyboardRemove())