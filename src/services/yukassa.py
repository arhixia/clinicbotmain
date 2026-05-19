import uuid
import logging
import aiohttp
from src.settings.config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, BOT_WEBHOOK_URL,BOT_USERNAME

logger = logging.getLogger(__name__)



class YukassaService:
    def __init__(self):
        self.shop_id = YOOKASSA_SHOP_ID
        self.secret_key = YOOKASSA_SECRET_KEY
        self.base_url = "https://api.yookassa.ru/v3"
        self.return_url = f"https://t.me/{BOT_USERNAME}"
        self.notification_url = f"{BOT_WEBHOOK_URL}/api/webhooks/yookassa"

    async def create_payment(self, amount:int, description:str, metadata:dict = None) ->str:
        headers = {
            "Idempotence-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        
        auth = aiohttp.BasicAuth(login=self.shop_id, password=self.secret_key)

        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": self.return_url 
            },
            "capture": True,
            "description": description,
            "metadata": metadata or {},
            "notification_url": self.notification_url 
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/payments",
                    json=payload,
                    headers=headers,
                    auth=auth
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['confirmation']['confirmation_url']
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка ЮKassa: {error_text}")
                        raise Exception("Yookassa API error")
        except Exception as e:
            logger.error(f"Exception in Yukassa service: {e}")
            raise e
        
        
yukassa_service = YukassaService()
