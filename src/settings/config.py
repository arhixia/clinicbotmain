from dotenv import load_dotenv
import os

load_dotenv()


#BOT
BOT_TOKEN = os.environ.get('BOT_TOKEN')
SUPPORT_USERNAME=os.environ.get('SUPPORT_USERNAME')
BOT_USERNAME=os.environ.get('BOT_USERNAME')

#DB
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT')
DB_NAME = os.environ.get('DB_NAME')
DB_PASS = os.environ.get('DB_PASS')
DB_USER = os.environ.get('DB_USER')


#REDIS
REDIS_URL = os.environ.get('REDIS_URL')


#AMOCRM
AMO_SECRET_KEY=os.environ.get('AMO_SECRET_KEY')
AMO_DOMAIN=os.environ.get('AMO_DOMAIN')
AMO_ACCESS_TOKEN=os.environ.get('AMO_ACCESS_TOKEN')

REFERRAL_PIPILINE_ID=int(os.environ.get('REFERRAL_PIPILINE_ID'))
PIPELINE_ID=int(os.environ.get('PIPELINE_ID'))
NEW_USERS_PIPELINE_ID=int(os.environ.get('NEW_USERS_PIPELINE_ID'))
CERTIFICATE_PIPELINE_ID=int(os.environ.get('CERTIFICATE_PIPELINE_ID'))


#YOOKASSA
YOOKASSA_SHOP_ID=os.environ.get('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY=os.environ.get('YOOKASSA_SECRET_KEY')

#URL
BOT_WEBHOOK_URL=os.environ.get('BOT_WEBHOOK_URL')

