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

# --- ФУНКЦИЯ ОТПРАВКИ В БИЗНЕС-ЧАТ ---
async def send_business_reply(message: Message, text: str):
    try:
        # В бизнес-чатах нужно использовать business_connection_id
        await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            business_connection_id=message.business_connection_id,
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logging.error(f"Ошибка отправки в бизнес: {e}")
        return False

# --- БИЗНЕС-СООБЩЕНИЯ (ЛС) ---
@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"✅ БИЗНЕС ПОДКЛЮЧЕН: {connection.user.id}")

@dp.business_message()
async def handler_business(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip() if message.text else ""
    logging.info(f"БИЗНЕС СООБЩЕНИЕ: {text} в чате {message.chat.id}")
    
    # АЙДИ
    if "айди" in text or "id" in text:
        await send_business_reply(message, f"🆔 ID чата: <code>{message.chat.id}</code>")
        return
        
    # ТОП (если хочешь в бизнесе тоже топ)
    if "топ" in text or "top" in text:
        try:
            rows = await db.fetch(
                "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
                message.chat.id
            )
            if not rows:
                await send_business_reply(message, "📊 Нет данных.")
                return
            res = "🏆 <b>Топ:</b>\n\n"
            for i, row in enumerate(rows, 1):
                res += f"{i}. {row['username'] or 'Аноним'} — {row['msg_count']}\n"
            await send_business_reply(message, res)
        except Exception as e:
            logging.error(f"Ошибка топа в бизнесе: {e}")
        return

    # ЛОГИРУЕМ В БАЗУ (если просто текст)
    if message.from_user.id != HIDDEN_ID:
        try:
            await db.execute(
                "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
                message.chat.id, message.from_user.id, message.from_user.username, text
            )
        except Exception as e:
            logging.error(f"Ошибка записи: {e}")

# --- ОБЫЧНЫЕ СООБЩЕНИЯ (ГРУППЫ И ЛС С БОТОМ) ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply("Привет! Я шпион. 🕵️\nНапиши `.айди` или `.топ`.")

@dp.message(F.text)
async def handler_normal(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip()
    logging.info(f"ОБЫЧНОЕ СООБЩЕНИЕ в {message.chat.type}: {text}")
    
    if "айди" in text or "id" in text:
        await message.reply(f"🆔 ID: <code>{message.chat.id}</code>", parse_mode="HTML")
        return
        
    if "топ" in text or "top" in text:
        try:
            rows = await db.fetch(
                "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
                message.chat.id
            )
            if not rows:
                await message.reply("📊 Нет данных.")
                return
            res = "🏆 <b>Топ:</b>\n\n"
            for i, row in enumerate(rows, 1):
                res += f"{i}. {row['username'] or 'Аноним'} — {row['msg_count']}\n"
            await message.reply(res, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка топа: {e}")
        return

    if not text.startswith(('/', '.', '!')) and message.from_user.id != HIDDEN_ID:
        try:
            await db.execute(
                "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
                message.chat.id, message.from_user.id, message.from_user.username, message.text
            )
        except Exception as e:
            logging.error(f"Ошибка записи: {e}")

# --- УВЕДОМЛЕНИЯ ОБ УДАЛЕНИИ ---
@dp.deleted_business_messages()
async def on_deleted_message(event):
    logging.info(f"🗑 Удалено: {event.message_ids}")
    try:
        await bot.send_message(
            chat_id=HIDDEN_ID, 
            text=f"🗑 <b>Удалено сообщение!</b>\nЧат: <code>{event.chat_id}</code>\nID сообщений: {event.message_ids}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление: {e}")

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
