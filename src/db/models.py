import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger, Column, ForeignKey, String, Integer, Text, DateTime,
    Enum as SAEnum, func,UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base


class CertificateStatus(str, enum.Enum):
    pending = "pending"    # создан, ожидает оплаты
    issued  = "issued"     # оплачен, активен
    declined = "declined"  # отменен или не оплачен
    used    = "used"  


class Certificate(Base):
    __tablename__ = "certificates"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
 
    buyer_telegram_id  = Column(String(32),  nullable=False)
    buyer_username     = Column(String(128), nullable=True)
    buyer_phone        = Column(String(20),  nullable=True)
    recipient_name     = Column(String(256), nullable=True)
    recipient_phone    = Column(String(20),  nullable=True)
    amount             = Column(Integer,     nullable=False)
    message            = Column(Text,        nullable=True)
    plan_name          = Column(String(128), nullable=False)
    yukassa_payment_id = Column(String(128), nullable=True, unique=True)
 
    status = Column(
        SAEnum(CertificateStatus, name="certificate_status"),
        nullable=False,
        default=CertificateStatus.pending,
        index=True,
    )
 
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paid_at    = Column(DateTime(timezone=True), nullable=True)
    issued_at  = Column(DateTime(timezone=True), nullable=True)
 
 
    def __repr__(self) -> str:
        return f"<Certificate id={self.id} amount={self.amount} status={self.status}>"

    

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger,primary_key=True)
    username = Column(String(128),nullable=True)
    ref_code = Column(String(32),nullable=False,unique=True,index=True)
    phone = Column(String(20),  nullable=True)

    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)

    referrals_sent = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer")
    referrals_received = relationship("Referral", foreign_keys="Referral.referred_id", back_populates="referred")

    def __repr__(self) -> str:
        return f"<User tg_id={self.telegram_id} ref_code={self.ref_code}>"



class Referral(Base):
    __tablename__ = "referrals"

    id = Column(UUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
    referrer_id = Column(BigInteger,ForeignKey("users.telegram_id"), nullable=False,index=True) #кто пригласил
    referred_id  = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)  # кого пригласили
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_sent")
    referred = relationship("User", foreign_keys=[referred_id], back_populates="referrals_received")

    __table_args__ = (
        UniqueConstraint(
            "referred_id", name="uq_referral_referred_id"
        ),
    )

    def __repr__(self) -> str:
        return f"<Referral referrer={self.referrer_id} → referred={self.referred_id}>"


