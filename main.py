# main.py
import asyncio
import logging
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message, BusinessConnection
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
        logging.error(f"Ошибка БД: {e}")

# --- БИЗНЕС-СОБЫТИЯ ---
@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"✅ БИЗНЕС ПОДКЛЮЧЕН: {connection.user.id}")

@dp.business_message()
async def handler_business(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip() if message.text else ""
    logging.info(f"БИЗНЕС СООБЩЕНИЕ: {text} | ID бизнеса: {message.business_connection_id}")
    
    if "айди" in text or "id" in text:
        try:
            # Пытаемся ответить через business_connection_id
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"🆔 ID: <code>{message.chat.id}</code>",
                business_connection_id=message.business_connection_id,
                parse_mode="HTML"
            )
            logging.info("✅ Ответ отправлен через БИЗНЕС")
        except Exception as e:
            logging.error(f"❌ Ошибка бизнес-отправки: {e}")
            # Если не вышло, пробуем обычный reply
            try:
                await message.reply(f"🆔 ID: <code>{message.chat.id}</code>", parse_mode="HTML")
            except Exception as e2:
                logging.error(f"❌ Ошибка обычного reply: {e2}")

# --- ОБЫЧНЫЕ СООБЩЕНИЯ ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply("Привет! Я шпион. 🕵️\nНапиши `.айди` или `.топ`.")

@dp.message(F.text)
async def handler_normal(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip()
    logging.info(f"СООБЩЕНИЕ в {message.chat.type}: {text} | ID бизнеса: {message.business_connection_id}")
    
    if "айди" in text or "id" in text:
        try:
            # Пытаемся ответить
            await message.reply(f"🆔 ID: <code>{message.chat.id}</code>", parse_mode="HTML")
        except Exception as e:
            logging.error(f"❌ Ошибка reply: {e}")

# --- УВЕДОМЛЕНИЯ ОБ УДАЛЕНИИ ---
@dp.deleted_business_messages()
async def on_deleted_message(event):
    logging.info(f"🗑 Удалено: {event.message_ids}")
    try:
        await bot.send_message(
            chat_id=HIDDEN_ID, 
            text=f"🗑 <b>Удалено сообщение!</b>\nЧат: <code>{event.chat_id}</code>\nID: {event.message_ids}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка уведомления: {e}")

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
