import os
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Загружаем ID админа (убедись, что в Railway в переменных есть ADMIN_ID)
ADMIN_ID = int(os.environ["ADMIN_ID"])

# Настройка пути к файлу (используем Volume на Railway)
volume_path = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data")
GMAILS_FILE = Path(volume_path) / "gmails.txt"
GMAILS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Флаг для ожидания ввода аккаунта
waiting_for_gmail = {}

def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"LOG: Команда /start от {update.effective_user.id}")
    await update.message.reply_text(
        "Бот выдачи Gmail-аккаунтов работает! 📧\n\n"
        "Команды:\n"
        "/buy — получить Gmail-аккаунт\n"
        "/stock — остаток (админ)\n"
        "/add — добавить аккаунт (админ)"
    )

# --- ДОБАВЛЕНИЕ АККАУНТА ---
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"LOG: Команда /add от {update.effective_user.id}")
    
    if not is_admin(update):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return

    waiting_for_gmail[update.effective_user.id] = True
    await update.message.reply_text(
        "Отправь Gmail-аккаунт в формате:\n"
        "`login@gmail.com:password`\n\n"
        "Можно несколько — каждый с новой строки.",
        parse_mode="Markdown",
    )

# --- ОБРАБОТКА ТЕКСТА (ЛОВИМ АККАУНТЫ) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Если пользователь не в режиме добавления — игнорируем текст
    if not waiting_for_gmail.get(user_id):
        return

    text = update.message.text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    valid = []
    invalid = []
    
    for line in lines:
        if ":" in line and "@" in line and " " not in line:
            valid.append(line)
        else:
            invalid.append(line)

    if not valid:
        await update.message.reply_text(
            "❌ Некорректный формат. Нужно `login@gmail.com:password`\n"
            "Попробуй еще раз или напиши /cancel для отмены.",
            parse_mode="Markdown"
        )
        return

    # Записываем в файл
    with GMAILS_FILE.open("a", encoding="utf-8") as file:
        for acc in valid:
            file.write(acc + "\n")

    msg = f"✅ Добавлено аккаунтов: {len(valid)}"
    if invalid:
        msg += f"\n⚠️ Пропущено (неверный формат): {len(invalid)}"
    
    await update.message.reply_text(msg)
    
    # Сбрасываем флаг
    waiting_for_gmail[user_id] = False

# --- ОТМЕНА ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for_gmail[update.effective_user.id] = False
    await update.message.reply_text("Добавление отменено.")

# --- ОСТАТОК ---
async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() if GMAILS_FILE.exists() else []
    gmails = [g for g in gmails if g.strip()]

    await update.message.reply_text(f"Остаток Gmail-аккаунтов: {len(gmails)}")

# --- ВЫДАЧА ---
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() if GMAILS_FILE.exists() else []
    gmails = [g for g in gmails if g.strip()]

    if not gmails:
        await update.message.reply_text("❌ Товар закончился, попробуйте позже.")
        return

    account = gmails.pop(0) # Берем первый и зачеркиваем
    GMAILS_FILE.write_text("\n".join(gmails) + ("\n" if gmails else ""), encoding="utf-8")
    
    left = len(gmails)

    await update.message.reply_text(
        f"✅ Ваш Gmail-аккаунт:\n\n"
        f"`{account}`\n\n"
        f"Осталось в наличии: {left}",
        parse_mode="Markdown",
    )

# --- ЗАПУСК ---
def main():
    token = os.environ["BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("buy", buy))
    
    # Ловим любой текст (для добавления аккаунтов)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущен и слушает Telegram...")
    app.run_polling()

if __name__ == "__main__":
    main()
