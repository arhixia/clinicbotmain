from datetime import datetime
import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from aiogram import Bot
import os

from sqlalchemy import select
from src.bot.routers.user_service import create_certificate_deal_in_crm
from src.db.database import AsyncSessionLocal
from src.db.models import Certificate, CertificateStatus
from src.settings.config import BOT_TOKEN, BOT_USERNAME, BOT_WEBHOOK_URL


router = APIRouter()
bot = Bot(token=BOT_TOKEN)


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
)


@router.post("/yookassa")
async def yookassa_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Вебхук от ЮKassa.
    1. Обновляет БД.
    2. Шлет сообщение в TG.
    3. Добавляет задачу в фон для отправки в CRM.
    """
    try:
        body = await request.json()
        event = body.get('event')

        if event != "payment.succeeded":
            return {"ok": True}
        
        payment_obj = body.get('object', {})
        metadata = payment_obj.get('metadata', {})
        cert_id = metadata.get('cert_id')

        if not cert_id:
            raise HTTPException(status_code=400, detail="No cert_id")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Certificate).where(Certificate.id == cert_id))
            cert = result.scalar_one_or_none()

            if not cert:
                raise HTTPException(status_code=404, detail="Cert not found")
                
            if cert.status == CertificateStatus.issued:
                return {"ok": True}
            
            cert.status = CertificateStatus.issued
            cert.yukassa_payment_id = payment_obj.get('id')
            cert.paid_at = datetime.now()
            cert.issued_at = datetime.now()
            await session.commit()

        cert_link = f"{BOT_WEBHOOK_URL}/api/cert/{cert_id}"

        message_text = (
            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
            f"Вы приобрели сертификат <b>AMCO CLINIC</b>.\n"
            f" Номинал: <b>{cert.amount} ₽</b>\n"
            f" Для кого: <i>{cert.recipient_name or 'Счастливчика'}</i>\n\n"
            f"🔗 <b>Ссылка на сертификат:</b>\n"
            f"<code>{cert_link}</code>\n\n"
            f"👇 <b>Что делать дальше?</b>\n"
            f"Перешлите эту ссылку тому, кому вы дарите сертификат!"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Открыть сертификат", url=cert_link)],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
        ])

        if cert.buyer_telegram_id:
            try:
                await bot.send_message(
                    chat_id=cert.buyer_telegram_id, 
                    text=message_text, 
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                logger.info(f"TG notified buyer {cert.buyer_telegram_id}")
            except Exception as e:
                logger.error(f"TG error: {e}")

        background_tasks.add_task(
            create_certificate_deal_in_crm,
            cert_id=str(cert.id),
            amount=cert.amount,
            buyer_tg_id=cert.buyer_telegram_id,
            buyer_phone=cert.buyer_phone,
            buyer_name=getattr(cert, 'buyer_name', None), 
            recipient_name=cert.recipient_name,
            recipient_phone=cert.recipient_phone,
            cert_link=cert_link
        )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")

    return {"ok": True}