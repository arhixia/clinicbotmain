import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from src.settings.config import SUPPORT_USERNAME, BOT_USERNAME
from src.db.database import AsyncSessionLocal
from src.bot.routers.user_service import (
    get_or_create_user, get_user_by_ref_code,
    register_referral, get_referral_stats,
    save_phone, get_user_phone,
)

logger = logging.getLogger(__name__)
router = Router()


class OnboardingStates(StatesGroup):
    waiting_for_phone = State()


PRIVACY_POLICY_URL = "https://amco.clinic/politicdata"


WELCOME_TEXT = """
✨ <b>Добро пожаловать в салон красоты!</b>

Мы рады видеть вас. Здесь вы можете:

🎁 <b>Купить подарочный сертификат</b> — порадуйте близких приятным подарком на любую сумму
📞 <b>Заказать обратный звонок</b> — оставьте номер, и мы перезвоним вам в ближайшее время
💬 <b>Написать в поддержку</b> — ответим на любые вопросы
🔗 <b>Пригласить друга</b> — делитесь реферальной ссылкой, мы фиксируем каждое приглашение


Выберите нужный раздел 👇
""".strip()


def get_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Подарочный сертификат", callback_data="cert_start")],
        [InlineKeyboardButton(text="📞 Обратный звонок",       callback_data="callback_start")],
        [InlineKeyboardButton(
            text="💬 Написать в поддержку",
            url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"
        )],
        [InlineKeyboardButton(text="🔗 Реферальная ссылка", callback_data="ref_info")],
    ])


def _phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user = message.from_user
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None

    async with AsyncSessionLocal() as session:
        db_user, is_new = await get_or_create_user(
            session=session,
            telegram_id=user.id,
            username=user.username,
        )

        if args and args.startswith("ref_") and is_new:
            await state.update_data(pending_ref_code=args)

        await session.commit()

    async with AsyncSessionLocal() as session:
        phone = await get_user_phone(session, user.id)

    if not phone:
        await state.set_state(OnboardingStates.waiting_for_phone)

        privacy_text = (
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Для начала работы поделитесь вашим номером телефона — "
            "это нужно для записи и обратного звонка.\n\n"
            f"Пользуясь ботом, вы соглашаетесь с нашей <a href='{PRIVACY_POLICY_URL}'>политикой конфиденциальности</a>."
        )
        
        await message.answer(
            text=privacy_text,
            reply_markup=_phone_keyboard(),
            parse_mode="HTML" 
        )
        return

    await message.answer(text=WELCOME_TEXT, reply_markup=get_main_menu())


@router.message(OnboardingStates.waiting_for_phone, F.contact)
async def handle_phone(message: Message, state: FSMContext) -> None:
    user = message.from_user
    phone = message.contact.phone_number
    data = await state.get_data()
    pending_ref_code = data.get("pending_ref_code")

    async with AsyncSessionLocal() as session:
        await save_phone(session, user.id, phone)
        try:
            from src.services.amo_crm import AmoCRMService
            amo = AmoCRMService()
            amo.create_new_user_lead(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                phone=phone
            )
        except Exception as e:
            logger.error(f"Не удалось отправить нового юзера в Amo: {e}")

        if pending_ref_code:
            referrer = await get_user_by_ref_code(session, pending_ref_code)
            if referrer:
                referrer_phone = await get_user_phone(session, referrer.telegram_id)
                
                await register_referral(
                    session=session,
                    referrer_id=referrer.telegram_id,
                    referred_id=user.id,
                    referrer_username=referrer.username,
                    referred_username=user.username,
                    referrer_phone=referrer_phone,
                    referred_phone=phone,
                )
                
                
        await session.commit()

    await state.clear()
    await message.answer(
        "✅ Номер сохранён!",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(text=WELCOME_TEXT, reply_markup=get_main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(text=WELCOME_TEXT, reply_markup=get_main_menu())


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(text=WELCOME_TEXT, reply_markup=get_main_menu())


@router.callback_query(F.data == "ref_info")
async def ref_info(callback: CallbackQuery) -> None:
    await callback.answer()
    user = callback.from_user

    async with AsyncSessionLocal() as session:
        db_user, _ = await get_or_create_user(session, user.id, user.username)
        stats = await get_referral_stats(session, user.id)
        await session.commit()

    ref_link = f"https://t.me/{BOT_USERNAME}?start={db_user.ref_code}"
    text = (
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 <b>Приглашено друзей:</b> {stats['total']}\n\n"
        f"Поделитесь ссылкой с друзьями — когда они зарегистрируются по вашей ссылке, "
        f"мы это зафиксируем и учтём при следующем визите 🎁"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться с другом",
            url=f"https://t.me/share/url?url={ref_link}&text=Присоединяйся+к+нам!"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])
    await callback.message.answer(text=text, reply_markup=keyboard)