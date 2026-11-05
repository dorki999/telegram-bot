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
GMAILS_FILE = Path("gmails.txt")
ADDING_GMAIL = 1
lock = asyncio.Lock()


def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот выдачи Gmail-аккаунтов работает! 📧\n\n"
        "Команды:\n"
        "/buy — получить Gmail-аккаунт\n"
        "/stock — остаток (админ)\n"
        "/add — добавить аккаунт (админ)"
    )


# ---------- АДМИН: ДОБАВЛЕНИЕ ----------

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END

    await update.message.reply_text(
        "Отправь Gmail-аккаунт в формате:\n"
        "`login@gmail.com:password`\n\n"
        "Можно несколько — каждый с новой строки.",
        parse_mode="Markdown",
    )
    return ADDING_GMAIL


async def add_gmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Разбираем: может быть несколько строк сразу
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    valid = []
    invalid = []
    for line in lines:
        # простая валидация: должен быть ":" и "@"
        if ":" in line and "@" in line and " " not in line:
            valid.append(line)
        else:
            invalid.append(line)

    if not valid:
        await update.message.reply_text(
            "❌ Некорректный формат. Нужно `login@gmail.com:password`",
            parse_mode="Markdown",
        )
        return ADDING_GMAIL

    async with lock:
        with GMAILS_FILE.open("a", encoding="utf-8") as file:
            for acc in valid:
                file.write(acc + "\n")

    msg = f"✅ Добавлено аккаунтов: {len(valid)}"
    if invalid:
        msg += f"\n⚠️ Пропущено (неверный формат): {len(invalid)}"

    await update.message.reply_text(msg)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END


# ---------- АДМИН: ОСТАТОК ----------

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    async with lock:
        gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() \
            if GMAILS_FILE.exists() else []
        gmails = [g for g in gmails if g.strip()]

    await update.message.reply_text(
        f"Остаток Gmail-аккаунтов: {len(gmails)}"
    )


# ---------- ВЫДАЧА (покупателю) ----------

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with lock:
        gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() \
            if GMAILS_FILE.exists() else []
        gmails = [g for g in gmails if g.strip()]

        if not gmails:
            await update.message.reply_text(
                "❌ Товар закончился, попробуйте позже."
            )
            return

        account = gmails.pop(0)  # берём первый и «зачёркиваем»
        GMAILS_FILE.write_text(
            "\n".join(gmails) + ("\n" if gmails else ""),
            encoding="utf-8",
        )
        left = len(gmails)

    await update.message.reply_text(
        f"✅ Ваш Gmail-аккаунт:\n\n"
        f"`{account}`\n\n"
        f"Осталось в наличии: {left}",
        parse_mode="Markdown",
    )


# ---------- ЗАПУСК ----------

def main():
    token = os.environ["BOT_TOKEN"]

    app = Application.builder().token(token).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADDING_GMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_gmail)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(conversation)
    app.add_handler(CommandHandler("stock", stock))

    app.run_polling()


if __name__ == "__main__":
    main()
