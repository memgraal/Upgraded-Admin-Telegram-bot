import os

import aiogram
import easyocr
import aiogram_fsm_sqlitestorage
import dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


dotenv.load_dotenv()


storage = aiogram_fsm_sqlitestorage.SQLiteStorage("states.db")
bot = aiogram.Bot(os.getenv("BOT_TOKEN"))
dp = aiogram.Dispatcher(storage=storage)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
ocr_reader = easyocr.Reader(
    ['ru', 'en'],
    gpu=False,  # True если есть CUDA
)
admin_user_id = os.getenv("BOT_ADMIN_ID")
_db_url = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_pre_ping=True,
)

session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False
)
