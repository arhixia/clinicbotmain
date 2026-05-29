import requests
import logging
from src.settings.config import AMO_ACCESS_TOKEN, AMO_DOMAIN, CERTIFICATE_PIPELINE_ID, NEW_USERS_PIPELINE_ID, PIPELINE_ID, REFERRAL_PIPILINE_ID

logger = logging.getLogger(__name__)


class AmoCRMService:
    def __init__(self):
        self.base_url = f"https://{AMO_DOMAIN}/api/v4"
        self.headers = {
            "Authorization": f"Bearer {AMO_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        logger.info(f"AmoCRM Service initialized. Domain: {AMO_DOMAIN}, Callback Pipeline ID: {PIPELINE_ID}")

    def create_new_user_lead(self, user_id, username, first_name, phone) -> int | None:
        try:
            logger.info(f"Creating new user lead for user_id={user_id}")
            contact_id = self._get_or_create_contact(tg_id=user_id, username=username, first_name=first_name, phone=phone)
            
            lead_name = f"Новый пользователь: @{username}" if username else f"New User ID {user_id}"
            
            payload = [{
                "name": lead_name,
                "pipeline_id": NEW_USERS_PIPELINE_ID,
                "_embedded": {
                    "contacts": [{"id": contact_id}],
                    "tags": [{"name": "Telegram Bot"}, {"name": "New User"}],
                },
            }]
            logger.debug(f"Payload for new user lead: {payload}")

            resp = requests.post(f"{self.base_url}/leads", headers=self.headers, json=payload)
            logger.info(f"AmoCRM Response Status: {resp.status_code}")
            logger.debug(f"AmoCRM Response Body: {resp.text}")
            
            resp.raise_for_status()
            lead_id = resp.json()["_embedded"]["leads"][0]["id"]
            logger.info(f"Сделка нового пользователя создана: {lead_id}")
            return lead_id
        except Exception as e:
            logger.error(f"Ошибка создания сделки нового пользователя: {e}", exc_info=True)
            return None
        

    def create_callback_lead(self, user_id, username, first_name, phone) -> int | None:
        try:
            logger.info(f"Creating callback lead for user_id={user_id}, phone={phone}")
            contact_id = self._get_or_create_contact(tg_id=user_id, username=username, first_name=first_name, phone=phone)
            logger.info(f"Contact ID for callback: {contact_id}")

            lead_name = f"Звонок: @{username}" if username else f"Звонок: {first_name or 'ID ' + str(user_id)}"
            
            payload = [{
                "name": lead_name,
                "pipeline_id": PIPELINE_ID,
                "_embedded": {
                    "contacts": [{"id": contact_id}],
                    "tags": [{"name": "Telegram"}, {"name": "Callback"}],
                },
            }]
            logger.debug(f"Payload for callback lead: {payload}")

            resp = requests.post(f"{self.base_url}/leads", headers=self.headers, json=payload)
            logger.info(f"AmoCRM Response Status: {resp.status_code}")
            logger.debug(f"AmoCRM Response Body: {resp.text}")

            resp.raise_for_status()
            lead_id = resp.json()["_embedded"]["leads"][0]["id"]
            logger.info(f"Сделка звонка создана: {lead_id}")
            return lead_id
        except Exception as e:
            logger.error(f"Ошибка создания сделки (callback): {e}", exc_info=True)
            return None

    def create_referral_lead(
        self,
        referrer_id: int,
        referrer_username: str | None,
        referred_id: int,
        referred_username: str | None,
        referrer_phone: str | None = None,
        referred_phone: str | None = None,
    ) -> int | None:
        try:
            logger.info(f"Creating referral lead: {referrer_id} -> {referred_id}")
            referrer_contact_id = self._get_or_create_contact(
                tg_id=referrer_id, username=referrer_username, phone=referrer_phone
            )
            referred_contact_id = self._get_or_create_contact(
                tg_id=referred_id, username=referred_username, phone=referred_phone
            )

            referrer_name = f"@{referrer_username}" if referrer_username else f"ID {referrer_id}"
            referred_name = f"@{referred_username}" if referred_username else f"ID {referred_id}"

            payload = [{
                "name": f"Реферал: {referrer_name} → {referred_name}",
                "pipeline_id": REFERRAL_PIPILINE_ID,
                "_embedded": {
                    "contacts": [
                        {"id": referrer_contact_id},
                        {"id": referred_contact_id},
                    ],
                    "tags": [{"name": "Telegram"}, {"name": "Referral"}],
                },
            }]
            logger.debug(f"Payload for referral lead: {payload}")

            resp = requests.post(f"{self.base_url}/leads", headers=self.headers, json=payload)
            logger.info(f"AmoCRM Response Status: {resp.status_code}")
            logger.debug(f"AmoCRM Response Body: {resp.text}")

            resp.raise_for_status()
            lead_id = resp.json()["_embedded"]["leads"][0]["id"]

            self._add_note(
                lead_id=lead_id,
                text=(
                    f"Реферальный переход через Telegram-бот\n\n"
                    f"Пригласил: {referrer_name} (TG ID: {referrer_id}){' | тел: ' + referrer_phone if referrer_phone else ''}\n"
                    f"Пришёл:    {referred_name} (TG ID: {referred_id}){' | тел: ' + referred_phone if referred_phone else ''}"
                ),
            )
            logger.info(f"Реферальная сделка создана: {lead_id}")
            return lead_id
        except Exception as e:
            logger.error(f"Ошибка создания реферальной сделки: {e}", exc_info=True)
            return None

    def _get_or_create_contact(self, tg_id, username, first_name=None, phone=None) -> int:
        logger.debug(f"Getting or creating contact for tg_id={tg_id}, phone={phone}")
        if phone:
            resp = requests.get(
                f"{self.base_url}/contacts", 
                headers=self.headers, 
                params={"query": phone}
            )
            logger.debug(f"Search contact response status: {resp.status_code}")
            if resp.status_code == 200:
                contacts = resp.json()['_embedded']['contacts']
                if contacts:
                    logger.info(f"Contact found by phone: {contacts[0]['id']}")
                    return contacts[0]['id']
        
        contact_name = f"@{username}" if username else first_name or f"TG_User_{tg_id}"
        contact_data = {"name": contact_name}
        custom_fields = []
        if phone:
            custom_fields.append({
                "field_code": "PHONE",
                "values": [{"value": phone, "enum_code": "MOB"}]
            }) 
        if custom_fields:
            contact_data["custom_fields_values"] = custom_fields

        logger.debug(f"Creating new contact with data: {contact_data}")
        resp = requests.post(f"{self.base_url}/contacts", headers=self.headers, json=[contact_data])
        logger.info(f"Create contact response status: {resp.status_code}")
        logger.debug(f"Create contact response body: {resp.text}")
        
        resp.raise_for_status()
        new_id = resp.json()["_embedded"]["contacts"][0]["id"]
        logger.info(f"New contact created: {new_id}")
        return new_id

    def _add_note(self, lead_id: int, text: str) -> None:
        try:
            logger.debug(f"Adding note to lead {lead_id}")
            resp = requests.post(
                f"{self.base_url}/leads/{lead_id}/notes",
                headers=self.headers,
                json=[{"entity_id": lead_id, "note_type": "common", "params": {"text": text}}],
            )
            logger.debug(f"Add note response status: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Не удалось добавить примечание: {e}")
        
    def create_certificate_lead(
        self,
        cert_id: str,
        amount: float,
        buyer_tg_id: int | None,
        buyer_phone: str | None,
        buyer_name: str | None = None,
        recipient_name: str | None = None,
        recipient_phone: str | None = None,
        cert_link: str | None = None,
    ) -> int | None:
        try:
            logger.info(f"Creating certificate lead for cert_id={cert_id}")
            buyer_contact_id = None
            if buyer_phone or buyer_tg_id:
                buyer_contact_id = self._get_or_create_contact(
                    tg_id=buyer_tg_id, 
                    username=None, 
                    first_name=buyer_name, 
                    phone=buyer_phone
                )

            recipient_contact_id = None
            if recipient_phone:
                 recipient_contact_id = self._get_or_create_contact(
                    tg_id=None, 
                    username=None, 
                    first_name=recipient_name, 
                    phone=recipient_phone
                )
                 
            lead_name = f"Сертификат #{cert_id[:8]}... - {amount} ₽"
            if recipient_name:
                lead_name += f" (Для: {recipient_name})"

            embedded_contacts = []
            if buyer_contact_id:
                embedded_contacts.append({"id": buyer_contact_id})
            if recipient_contact_id:
                embedded_contacts.append({"id": recipient_contact_id})

            payload = [{
                "name": lead_name,
                "pipeline_id": CERTIFICATE_PIPELINE_ID, 
                "price": amount,
                "_embedded": {
                    "contacts": embedded_contacts,
                    "tags": [{"name": "Certificate"}, {"name": "YooKassa"}],
                },
            }]
            logger.debug(f"Payload for certificate lead: {payload}")

            resp = requests.post(f"{self.base_url}/leads", headers=self.headers, json=payload)
            logger.info(f"AmoCRM Response Status: {resp.status_code}")
            logger.debug(f"AmoCRM Response Body: {resp.text}")

            resp.raise_for_status()
            lead_id = resp.json()["_embedded"]["leads"][0]["id"]
            
            logger.info(f"Сделка сертификата создана в AmoCRM: {lead_id}")

            note_text = (
                f"Детали покупки сертификата\n\n"
                f"ID Сертификата: {cert_id}\n"
                f"Сумма: {amount} ₽\n"
                f"Покупатель TG ID: {buyer_tg_id}\n"
                f"Телефон покупателя: {buyer_phone or 'Не указан'}\n"
                f"Получатель: {recipient_name or 'Не указан'}\n"
                f"Телефон получателя: {recipient_phone or 'Не указан'}\n\n"
                f"Ссылка на сертификат:  {cert_link}"
            )
            
            self._add_note(lead_id=lead_id, text=note_text)

            return lead_id

        except Exception as e:
            logger.error(f"Ошибка создания сделки сертификата в AmoCRM: {e}", exc_info=True)
            return None