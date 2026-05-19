import uuid
import hashlib
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.amo_crm import AmoCRMService
from src.db.models import User, Referral
amo_service = AmoCRMService()


logger = logging.getLogger(__name__)


def _generate_ref_code(telegram_id: int) -> str:
    h = hashlib.sha256(str(telegram_id).encode()).hexdigest()[:8]
    return f"ref_{h}"


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
) -> tuple[User, bool]:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        return user, False
    user = User(
        telegram_id=telegram_id,
        username=username,
        ref_code=_generate_ref_code(telegram_id),
    )
    session.add(user)
    await session.flush()
    logger.info(f"Новый пользователь: {telegram_id} (@{username})")
    return user, True


async def save_phone(
    session: AsyncSession,
    telegram_id: int,
    phone: str,
) -> None:
    """Сохраняет номер телефона юзера."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.phone = phone
        logger.info(f"Телефон сохранён: {telegram_id} → {phone}")


async def get_user_phone(
    session: AsyncSession,
    telegram_id: int,
) -> str | None:
    """Возвращает сохранённый телефон юзера или None."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    return user.phone if user else None


async def register_referral(
    session: AsyncSession,
    referrer_id: int,
    referred_id: int,
    referrer_username: str | None = None,
    referred_username: str | None = None,
    referrer_phone: str | None = None,
    referred_phone: str | None = None,
) -> bool:
    if referrer_id == referred_id:
        return False

    existing = await session.execute(select(Referral).where(Referral.referred_id == referred_id))
    if existing.scalar_one_or_none():
        return False

    referrer_result = await session.execute(select(User).where(User.telegram_id == referrer_id))
    if not referrer_result.scalar_one_or_none():
        logger.warning(f"Referrer {referrer_id} не найден в БД")
        return False

    session.add(Referral(id=uuid.uuid4(), referrer_id=referrer_id, referred_id=referred_id))
    logger.info(f"Реферал зафиксирован в БД: {referrer_id} → {referred_id}")

    try:
        from src.services.amo_crm import AmoCRMService
        AmoCRMService().create_referral_lead(
            referrer_id=referrer_id,
            referrer_username=referrer_username,
            referrer_phone=referrer_phone,
            referred_id=referred_id,
            referred_username=referred_username,
            referred_phone=referred_phone,
        )
    except Exception as e:
        logger.error(f"Ошибка отправки реферала в amoCRM (БД сохранена): {e}")

    return True


async def get_referral_stats(session: AsyncSession, telegram_id: int) -> dict:
    count = (await session.execute(
        select(func.count()).where(Referral.referrer_id == telegram_id)
    )).scalar_one()
    recent = (await session.execute(
        select(Referral).where(Referral.referrer_id == telegram_id)
        .order_by(Referral.created_at.desc()).limit(5)
    )).scalars().all()
    return {"total": count, "recent": recent}


async def get_user_by_ref_code(session: AsyncSession, ref_code: str) -> User | None:
    return (await session.execute(
        select(User).where(User.ref_code == ref_code)
    )).scalar_one_or_none()


def create_certificate_deal_in_crm(
    cert_id: str,
    amount: float,
    buyer_tg_id: int | None,
    buyer_phone: str | None,
    buyer_name: str | None,
    recipient_name: str | None,
    recipient_phone: str | None,
    cert_link: str
):
    """
    Синхронная функция для создания сделки в AmoCRM.
    Вызывается в фоне, поэтому может использовать blocking requests.
    """
    try:
        logger.info(f"Starting CRM task for cert {cert_id}")
        
        lead_id = amo_service.create_certificate_lead(
            cert_id=cert_id,
            amount=amount,
            buyer_tg_id=buyer_tg_id,
            buyer_phone=buyer_phone,
            buyer_name=buyer_name,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            cert_link=cert_link
        )
        
        if lead_id:
            logger.info(f"Successfully created CRM deal {lead_id} for cert {cert_id}")
        else:
            logger.error(f"Failed to create CRM deal for cert {cert_id}")
            
    except Exception as e:
        logger.error(f"Critical error in CRM background task for cert {cert_id}: {e}", exc_info=True)