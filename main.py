
import os
import asyncio
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

ADMIN_ID = int(os.environ["ADMIN_ID"])
KEYS_FILE = Path("keys.txt")
ADDING_KEY = 1
lock = asyncio.Lock()


def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот выдачи игровых ключей работает! 🎮"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END

    await update.message.reply_text("Отправь игровой ключ:")
    return ADDING_KEY


async def add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip()

    if not key or "\n" in key:
        await update.message.reply_text("Некорректный ключ.")
        return ADDING_KEY

    async with lock:
        with KEYS_FILE.open("a", encoding="utf-8") as file:
            file.write(key + "\n")

    await update.message.reply_text("Ключ добавлен! ✅")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END


async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    async with lock:
        keys = KEYS_FILE.read_text(encoding="utf-8").splitlines() \
            if KEYS_FILE.exists() else []

    await update.message.reply_text(
        f"Остаток игровых ключей: {len(keys)}"
    )


async def take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    async with lock:
        keys = KEYS_FILE.read_text(encoding="utf-8").splitlines() \
            if KEYS_FILE.exists() else []

        if not keys:
            await update.message.reply_text("Ключей нет!")
            return

        key = keys.pop(0)
        KEYS_FILE.write_text(
            "\n".join(keys) + ("\n" if keys else ""),
            encoding="utf-8"
        )

    await update.message.reply_text(f"Тестовая выдача:\n{key}")


def main():
    token = os.environ["BOT_TOKEN"]

    app = Application.builder().token(token).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADDING_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_key)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conversation)
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("take", take))

    app.run_polling()


if __name__ == "__main__":
    main()
