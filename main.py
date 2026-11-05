import os
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

# --- ИМПОРТЫ ДЛЯ PLAYEROK ---
from playerokapi.account import Account
from playerokapi.listener.listener import EventListener
from playerokapi.enums import EventTypes

# --- НАСТРОЙКИ ---
ADMIN_ID = int(os.environ["ADMIN_ID"])
BOT_TOKEN = os.environ["BOT_TOKEN"]

# ВСТАВЬ СВОИ ДАННЫЕ ОТ PLAYEROK СЮДА!
PLAYEROK_COOKIES = "__ddg1_=t0qUlq2ISMNcEu56rViu; auid=39289f4f-740b-4451-8213-e3534fdaca1f; fakeauid=2270c3dbb7703ee92f6efd1ef2da848d; need_page_reload=false; _ym_uid=1793833619638516294; _ym_d=1793833619; _ym_isad=2; tmr_lvid=ebd8e397224e85533ac58c1ba08e4ca1; tmr_lvidTS=1793833622315; _tt_enable_cookie=1; _ttp=01M6MD1QM1043M1M3JQ4XAGDVJ_.tt.1.1793833623170; cra-events-id=1793833623942204; domain_sid=iLnbBsmileOWZllOseW_d%3A1793833624052; mdd=0; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxZjAzNDNhNy0xZWY5LTY2YzAtZGFkMi0wMzBmZDE4ZjQ1ZmIiLCJpZGVudGl0eSI6IiIsInJvbGUiOiJVU0VSIiwic2lkIjoiMDFhMWE4ZDgtMDMzOC03MmZiLTkyODAtM2VjMjRmY2E1ODU4IiwicmV2IjoxLCJ2IjoxLCJpYXQiOjE3OTM4MzQwOTEsImV4cCI6MTgyNTM3MDA5MSwianRpIjoiN2I4YTg2MzQtZDFmZi00NzFmLTliZDMtYjk5MzExNDZhYWJkIn0.Gmw4vHjklvqpZmRnJvATyk76gFeAv3CSnSzzHr3uygc; _iidt=glBVNtb3aSzPaG+G8zyS8Q7D9U6mS8Zx3Q0wVVI9E4CGthQBpR+V8jXt6HjXPJC+kuFWMGR173ZXZsy+9Bof0etG+D4E7fE=; _vid_t=KeO61HxRtdkZsppiXCZsvswPjQs/LGNKDcK32OdFw5AoCUugLZspL7tE5ckB+wWi7O6yBWJsmmt4UI3ifM70Zzq5KxGsMpU=; listing_seed=3287570200; __ddg9_=85.113.214.150; ttcsid=1793898297100::eJWeDKGfpbXiaRQj0E2i.3.1793898415188.0::0.108399.114705::0.0.0.0::0.0.0; ttcsid_D3OFSBRC77UED4260FFG=1793898297092::FUU3uzQdqgYtBicZFLpF.3.1793898415193.1; __ddg8_=u4DXjSU5P0ySEplK; __ddg10_=1793898419; tmr_detect=0%7C1793898420684"
PLAYEROK_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"

# Файл для Gmail (используем Volume на Railway)
volume_path = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data")
GMAILS_FILE = Path(volume_path) / "gmails.txt"
GMAILS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Флаг для ожидания ввода аккаунта
waiting_for_gmail = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

def take_gmail_from_file():
    if not GMAILS_FILE.exists():
        return None
    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines()
    gmails = [g for g in gmails if g.strip()]
    if not gmails:
        return None
    account = gmails.pop(0)
    GMAILS_FILE.write_text("\n".join(gmails) + ("\n" if gmails else ""), encoding="utf-8")
    return account

# --- КОМАНДЫ ТЕЛЕГРАМ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот выдачи Gmail-аккаунтов работает! 📧\n"
        "Автовыдача на Playerok включена."
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    waiting_for_gmail[update.effective_user.id] = True
    await update.message.reply_text(
        "Отправь Gmail-аккаунт в формате:\n"
        "`login@gmail.com:password`\n"
        "Можно несколько — каждый с новой строки.",
        parse_mode="Markdown",
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not waiting_for_gmail.get(user_id):
        return
    text = update.message.text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    valid = [line for line in lines if ":" in line and "@" in line and " " not in line]
    if not valid:
        await update.message.reply_text("❌ Некорректный формат. Нужно `login@gmail.com:password`")
        return
    with GMAILS_FILE.open("a", encoding="utf-8") as file:
        for acc in valid:
            file.write(acc + "\n")
    await update.message.reply_text(f"✅ Добавлено аккаунтов: {len(valid)}")
    waiting_for_gmail[user_id] = False

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for_gmail[update.effective_user.id] = False
    await update.message.reply_text("Добавление отменено.")

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() if GMAILS_FILE.exists() else []
    gmails = [g for g in gmails if g.strip()]
    await update.message.reply_text(f"Остаток Gmail-аккаунтов: {len(gmails)}")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account = take_gmail_from_file()
    if not account:
        await update.message.reply_text("❌ Товар закончился.")
        return
    gmails = GMAILS_FILE.read_text(encoding="utf-8").splitlines() if GMAILS_FILE.exists() else []
    left = len([g for g in gmails if g.strip()])
    await update.message.reply_text(
        f"✅ Ваш Gmail-аккаунт:\n\n`{account}`\n\nОсталось: {left}",
        parse_mode="Markdown",
    )

# --- ИНТЕГРАЦИЯ С PLAYEROK (В ОТДЕЛЬНОМ ПОТОКЕ) ---
def playerok_listener_thread():
    print("Запуск слушателя Playerok...")
    try:
        acc = Account(
            cookies=PLAYEROK_COOKIES,
            user_agent=PLAYEROK_USER_AGENT
        ).get()
        
        listener = EventListener(acc)
        
        for event in listener.listen():
            # ЛОВИМ СОБЫТИЕ НОВОГО ЗАКАЗА
            if event.type is EventTypes.NEW_DEAL: 
                print(f"Новый заказ! ID: {event.deal.id}")
                gmail_acc = take_gmail_from_file()
                
                if gmail_acc:
                    chat_id = event.deal.chat_id 
                    acc.send_message(
                        chat_id=chat_id,
                        text=f"🤖 Автовыдача!\nВаш Gmail аккаунт:\n`{gmail_acc}`\n\nПожалуйста, смените пароль при первом входе."
                    )
                    print(f"Аккаунт {gmail_acc} выдан.")
                else:
                    acc.send_message(
                        chat_id=chat_id,
                        text="⚠️ Извините, товар временно закончился. Напишите продавцу."
                    )
                    print("ОШИБКА: Нет аккаунтов для выдачи!")
                    
    except Exception as e:
        print(f"Ошибка в Playerok: {e}")

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
