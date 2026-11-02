# main.py
import asyncio
import logging
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message, BusinessConnection
from aiogram.filters import CommandStart, Command
import config

session = AiohttpSession(api=TelegramAPIServer.from_base(config.API_SERVER))
bot = Bot(token=config.BOT_TOKEN, session=session)
dp = Dispatcher()

# --- ТВОЙ ID И НИК ДЛЯ СКРЫТИЯ ---
HIDDEN_ID = 1780243499
HIDDEN_USERNAME = "zovx"

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
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

# --- КОМАНДА /id ---
@dp.message(Command("id"))
async def get_chat_id(message: Message):
    if message.from_user.id == HIDDEN_ID or (message.from_user.username and message.from_user.username.lower() == HIDDEN_USERNAME):
        await message.reply("🕵️ Пользователь скрыт")
        return
    await message.reply(f"🆔 ID этого чата: <code>{message.chat.id}</code>", parse_mode="HTML")

# --- БИЗНЕС СОБЫТИЯ (ЛС) ---
@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"Подключен бизнес-аккаунт: {connection.user.id}")

@dp.business_message()
async def on_business_message(message: Message, db: asyncpg.Pool):
    # Если пишет скрытый юзер - не логируем
    if message.from_user.id == HIDDEN_ID or (message.from_user.username and message.from_user.username.lower() == HIDDEN_USERNAME):
        return
        
    text = message.text or "[Медиа]"
    await db.execute(
        "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
        message.chat.id, message.from_user.id, message.from_user.username, text
    )

# --- ЛОВИМ СООБЩЕНИЯ В ГРУППАХ ---
@dp.message(F.content_type == "text")
async def log_group_messages(message: Message, db: asyncpg.Pool):
    if message.text and message.text.startswith(('.', '/')):
        return
        
    # Если пишет скрытый юзер - не логируем
    if message.from_user.id == HIDDEN_ID or (message.from_user.username and message.from_user.username.lower() == HIDDEN_USERNAME):
        return
        
    await db.execute(
        "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
        message.chat.id, message.from_user.id, message.from_user.username, message.text
    )

# --- СТАТИСТИКА ---
@dp.message(Command("топ"))
async def cmd_top(message: Message, db: asyncpg.Pool):
    rows = await db.fetch(
        "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
        message.chat.id
    )
    
    if not rows:
        await message.reply("📊 Нет данных для статистики в этом чате.")
        return

    text = "🏆 <b>Топ-10 активных в чате:</b>\n\n"
    for i, row in enumerate(rows, 1):
        # Если в топе оказался скрытый юзер - пишем "Пользователь скрыт"
        if row['username'] and row['username'].lower() == HIDDEN_USERNAME:
            name = "Пользователь скрыт"
        else:
            name = f"@{row['username']}" if row['username'] else "Аноним"
        text += f"{i}. {name} — {row['msg_count']} сообщений\n"

    await message.reply(text, parse_mode="HTML")

@dp.message(Command("стат"))
async def cmd_stats(message: Message, db: asyncpg.Pool):
    total = await db.fetchval("SELECT COUNT(*) FROM chat_stats WHERE chat_id = $1", message.chat.id)
    if not total:
        await message.reply("📊 В этом чате пока нет данных.")
        return
    text = f"📈 <b>Статистика чата:</b>\n\n💬 Всего сообщений: <b>{total}</b>"
    await message.reply(text, parse_mode="HTML")

@dp.message(F.text.lower() == ".я")
async def cmd_me(message: Message, db: asyncpg.Pool):
    # Если скрытый юзер - пишем заглушку
    if message.from_user.id == HIDDEN_ID or (message.from_user.username and message.from_user.username.lower() == HIDDEN_USERNAME):
        await message.reply("🕵️ Пользователь скрыт")
        return

    total = await db.fetchval(
        "SELECT COUNT(*) FROM chat_stats WHERE chat_id = $1 AND user_id = $2",
        message.chat.id, message.from_user.id
    )
    if not total:
        await message.reply("📊 Ты еще не писал в этом чате.")
        return
    await message.reply(f"👤 <b>Твоя статистика в этом чате:</b>\n\n💬 Сообщений: <b>{total}</b>", parse_mode="HTML")

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    pool = await asyncpg.create_pool(config.DATABASE_URL)
    await init_db(pool)
    
    dp["db"] = pool
    logging.info("Шпион активирован. Твой профиль скрыт.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
