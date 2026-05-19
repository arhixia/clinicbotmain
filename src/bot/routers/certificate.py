import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from src.db.models import Certificate, CertificateStatus
from src.settings.config import BOT_USERNAME
from src.bot.states.cert_states import CertificateStates
from src.bot.routers.user_service import get_user_phone
from src.db.database import AsyncSessionLocal
from src.services.yukassa import yukassa_service
import logging


logger = logging.getLogger()


router = Router()

 
AMOUNTS = [3000, 5000, 10000, 15000, 25000, 30000, 50000]



def _validate_ru_phone(phone: str) -> str | None:
    """
    Валидирует российский номер телефона.
    Возвращает нормализованный номер (+7...) или None, если номер неверный.
    """
    clean_phone = re.sub(r'[^\d+]', '', phone)

    if clean_phone.startswith('8'):
        clean_phone = '+7' + clean_phone[1:]
    elif clean_phone.startswith('7'):
        clean_phone = '+' + clean_phone
        
    if re.match(r'^\+7[0-9]{10}$', clean_phone):
        return clean_phone
    
    return None


#КЛАВИАТУРЫ


def kb_amounts() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i,amount in enumerate(AMOUNTS):
        row.append(
            InlineKeyboardButton(
            text=f"{amount:,}".replace(",", " ") + " ₽",
            callback_data=f"cert_amount_{amount}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(
        text="✏️ Другая сумма",
        callback_data="cert_amount_custom",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_skip() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data="cert_skip")],
    ])
 
 
def kb_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить",    callback_data="cert_pay")],
        [InlineKeyboardButton(text="Изменить", callback_data="cert_edit")],
    ])

def _format_amount(amount:int) -> str:
    return f"{amount:,}".replace(",", " ")


def _preview_text(data: dict) -> str:
    amount  = _format_amount(data["amount"])
    name    = data.get("recipient_name") or "—"
    phone   = data.get("recipient_phone") or "—"
    msg     = data.get("message") or "—"
    return (
        f"🎁 <b>Проверьте заказ:</b>\n\n"
        f"💰 Номинал: <b>{amount} ₽</b>\n"
        f"👤 Кому: <b>{name}</b>\n"
        f"📱 Телефон: <code>{phone}</code>\n"
        f"💬 Сообщение: <i>{msg}</i>\n\n"
        f"Всё верно?"
    )





#ВЫБОР НОМИНАЛА


@router.callback_query(F.data == "cert_start")
async def cert_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(CertificateStates.choosing_amount)
    await callback.message.answer(
        "🎁 <b>Подарочный сертификат</b>\n\n"
        "Выберите номинал:",
        reply_markup=kb_amounts(),
    )


@router.callback_query(F.data.startswith("cert_amount_"), CertificateStates.choosing_amount)
async def cert_choose_amount(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    value = callback.data.removeprefix("cert_amount_")

    if value == "custom":
        await state.set_state(CertificateStates.entering_amount)
        await callback.message.answer(
            "Введите сумму в рублях (например: <code>7500</code>):\n"
            "<i>Минимум 1 000 ₽</i>"
        )
        return
    
    await state.update_data(amount=int(value))
    await _ask_recipient_name(callback.message, state)


@router.message(CertificateStates.entering_amount)
async def cert_enter_amount(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "").replace("\xa0", "")
    if not text.isdigit():
        await message.answer("Введите только цифры, без пробелов и знаков.")
        return

    amount = int(text)
    if amount < 1000:
        await message.answer("Минимальная сумма — <b>1 000 ₽</b>. Введите другую сумму:")
        return

    await state.update_data(amount=amount)
    await _ask_recipient_name(message, state)




#ИМЯ ПОЛУЧАТЕЛЯ 


async def _ask_recipient_name(target, state: FSMContext):
    await state.set_state(CertificateStates.entering_name)
    await target.answer(
        "Введите имя получателя или нажмите «Пропустить»:",
        reply_markup=kb_skip(),
    )


@router.message(CertificateStates.entering_name)
async def cert_enter_name(message: Message, state: FSMContext):
    await state.update_data(recipient_name=message.text.strip())
    await _ask_recipient_phone(message, state)
 
 
@router.callback_query(F.data == "cert_skip", CertificateStates.entering_name)
async def cert_skip_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(recipient_name=None)
    await _ask_recipient_phone(callback.message, state)


#ТЕЛЕФОН ПОЛУЧАТЕЛЯ


async def _ask_recipient_phone(target, state: FSMContext):
    await state.set_state(CertificateStates.entering_recipient_phone)
    await target.answer(
        "📱 <b>Телефон получателя</b>\n\n"
        "Введите номер в формате +79990000000.\n"
        "На него придет ссылка на сертификат.",
        reply_markup=kb_skip()
    )


@router.message(CertificateStates.entering_recipient_phone)
async def cert_enter_recipient_phone(message: Message, state: FSMContext):
    valid_phone = _validate_ru_phone(message.text)
    
    if not valid_phone:
        await message.answer(
            "❌ Неверный формат номера.\n"
            "Попробуйте еще раз в формате +79991234567."
        )
        return
    
    await state.update_data(recipient_phone=valid_phone)
    await _ask_message(message, state)


@router.callback_query(F.data == "cert_skip", CertificateStates.entering_recipient_phone)
async def cert_skip_recipient_phone(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with AsyncSessionLocal() as session:
        buyer_phone = await get_user_phone(session, callback.from_user.id)
        if buyer_phone:
             validated_buyer = _validate_ru_phone(buyer_phone)
             if validated_buyer:
                 buyer_phone = validated_buyer
                 
        await state.update_data(recipient_phone=buyer_phone)
        
    await _ask_message(callback.message, state)


#СООБЩЕНИЕ


async def _ask_message(target, state: FSMContext):
    await state.set_state(CertificateStates.entering_message)
    await target.answer(
        "Напишите поздравление или нажмите «Пропустить»:",
        reply_markup=kb_skip(),
    )


@router.message(CertificateStates.entering_message)
async def cert_enter_message(message: Message, state: FSMContext):
    await state.update_data(message=message.text.strip())
    await _show_preview(message, state)
 
 
@router.callback_query(F.data == "cert_skip", CertificateStates.entering_message)
async def cert_skip_message(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(message=None)
    await _show_preview(callback.message, state)
 
 
async def _show_preview(target, state: FSMContext):
    data = await state.get_data()
    await state.set_state(CertificateStates.confirming)
    await target.answer(
        _preview_text(data),
        reply_markup=kb_confirm(),
    )



#ПОДТВЕРЖДЕНИЕ -> ОПЛАТА

@router.callback_query(F.data == "cert_pay", CertificateStates.confirming)
async def cert_pay(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    
    user = callback.from_user
    
    async with AsyncSessionLocal() as session:
        buyer_phone = await get_user_phone(session, user.id)
        
        new_cert = Certificate(
            buyer_telegram_id=str(user.id),
            buyer_username=user.username,
            buyer_phone=buyer_phone,
            recipient_name=data.get("recipient_name"),
            recipient_phone=data.get("recipient_phone"),
            amount=data["amount"],
            message=data.get("message"),
            status=CertificateStatus.pending, 
            plan_name="Подарочный сертификат"
        )
        session.add(new_cert)
        await session.commit()
        await session.refresh(new_cert)

    try:
        payment_url = await yukassa_service.create_payment(
            amount=data["amount"],
            description=f"Сертификат AMCO для {data.get('recipient_name')}",
            metadata={"cert_id": str(new_cert.id)} 
        )
        
        await callback.message.answer(
            f"💳 <b>Оплата заказа</b>\n\n"
            f"Сумма: <b>{_format_amount(data['amount'])} ₽</b>\n"
            f"Нажмите кнопку ниже, чтобы оплатить картой.\n",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить картой", url=payment_url)]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        await callback.message.answer(" Ошибка при создании платежа. Попробуйте позже.")
    
    await state.clear()



@router.callback_query(F.data == "cert_edit", CertificateStates.confirming)
async def cert_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(CertificateStates.choosing_amount)
    await callback.message.answer(
        "Давайте заполним данные заново.\n\nВыберите номинал:",
        reply_markup=kb_amounts(),
    )


