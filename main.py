import os
import os
import certifi

# ПРИНУДИТЕЛЬНО УКАЗЫВАЕМ БИБЛИОТЕКЕ ПРАВИЛЬНЫЙ ПУТЬ К СЕРТИФИКАТАМ
cert_path = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = cert_path
os.environ["SSL_CERT_FILE"] = cert_path

# Дополнительная страховка для библиотеки PyPlayerokAPI
try:
    import PyPlayerokAPI
    # Если библиотека ищет файл внутри себя, мы можем попытаться подменить путь
    # (это сработает, если библиотека использует переменную окружения внутри)
    os.environ["PYPLAYEROK_CACERT"] = cert_path
except ImportError:
    pass
# --- ОБХОД ОШИБКИ CACERT.PEM ---
# Указываем библиотеке, где лежат стандартные сертификаты, чтобы она не искала их в папке PyPlayerokAPI
os.environ["REQUESTS_CA_BUNDLE"] = "/app/.venv/lib/python3.13/site-packages/certifi/cacert.pem"
os.environ["SSL_CERT_FILE"] = "/app/.venv/lib/python3.13/site-packages/certifi/cacert.pem"

import threading
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- НОВАЯ БИБЛИОТЕКА PLAYEROK ---
from PyPlayerokAPI.account import AccountClient
from PyPlayerokAPI.stream import PlayerokAccountListener
from PyPlayerokAPI.stream.events import PlayerokEvent

# --- НАСТРОЙКИ ---
ADMIN_ID = int(os.environ["ADMIN_ID"])
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Берем токен и агент из переменных окружения Railway
PLAYEROK_TOKEN = os.environ.get("PLAYEROK_TOKEN", "")
PLAYEROK_USER_AGENT = os.environ.get("PLAYEROK_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

# Файл для Gmail (используем Volume на Railway)
volume_path = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data")
GMAILS_FILE = Path(volume_path) / "gmails.txt"
GMAILS_FILE.parent.mkdir(parents=True, exist_ok=True)

waiting_for_gmail = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

def take_gmail_from_file():
    if not GMAILS_FILE.exists(): return None
    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines()
    gmails = [g for g in gmails if g.strip()]
    if not gmails: return None
    account = gmails.pop(0)
    GMAILS_FILE.write_text("\n".join(gmails) + ("\n" if gmails else ""), encoding="utf-8")
    return account

# --- КОМАНДЫ ТЕЛЕГРАМ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот выдачи Gmail работает. Автовыдача на Playerok включена.")

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    waiting_for_gmail[update.effective_user.id] = True
    await update.message.reply_text("Отправь Gmail в формате:\n`login@gmail.com:password`", parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not waiting_for_gmail.get(user_id): return
    text = update.message.text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    valid = [line for line in lines if ":" in line and "@" in line and " " not in line]
    if not valid:
        await update.message.reply_text("❌ Некорректный формат.")
        return
    with GMAILS_FILE.open("a", encoding="utf-8") as file:
        for acc in valid: file.write(acc + "\n")
    await update.message.reply_text(f"✅ Добавлено: {len(valid)}")
    waiting_for_gmail[user_id] = False

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for_gmail[update.effective_user.id] = False
    await update.message.reply_text("Отменено.")

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() if GMAILS_FILE.exists() else []
    gmails = [g for g in gmails if g.strip()]
    await update.message.reply_text(f"Остаток: {len(gmails)}")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account = take_gmail_from_file()
    if not account:
        await update.message.reply_text("❌ Товар закончился.")
        return
    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() if GMAILS_FILE.exists() else []
    left = len([g for g in gmails if g.strip()])
    await update.message.reply_text(f"✅ Ваш Gmail:\n\n`{account}`\n\nОсталось: {left}", parse_mode="Markdown")

# --- ИНТЕГРАЦИЯ С PLAYEROK ---
def playerok_listener_thread():
    print("Запуск слушателя Playerok...")
    
    async def run_listener():
        try:
            account = AccountClient(token=PLAYEROK_TOKEN, user_agent=PLAYEROK_USER_AGENT)
            listener = PlayerokAccountListener(account)
            router = listener.router

            @router.on_new_deal()
            async def on_new_deal(account: AccountClient, event: PlayerokEvent):
                print(f"🔥 Новый заказ! ID сделки: {event.deal.id}")
                
                gmail_acc = take_gmail_from_file()
                chat_id = event.chat.id if event.chat else None
                
                if not chat_id:
                    print("❌ Ошибка: не удалось получить ID чата.")
                    return

                if gmail_acc:
                    await account.send_message(chat_id, f"🤖 Автовыдача!\nВаш Gmail: `{gmail_acc}`\n\nСмените пароль при входе.")
                    print(f"✅ Аккаунт {gmail_acc} выдан.")
                else:
                    await account.send_message(chat_id, "⚠️ Товар временно закончился.")
                    print("❌ Ошибка: нет аккаунтов!")

            listener.start()
            await asyncio.Event().wait() # Держим поток живым

        except Exception as e:
            print(f"❌ Критическая ошибка в Playerok: {e}")

    import asyncio
    asyncio.run(run_listener())

# --- ЗАПУСК ---
def main():
    # Запускаем Playerok в фоновом потоке
    thread = threading.Thread(target=playerok_listener_thread, daemon=True)
    thread.start()

    # Запускаем Telegram бота
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Telegram бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
