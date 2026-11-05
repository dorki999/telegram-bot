import os
import ssl
import asyncio
from pathlib import Path
from email.message import EmailMessage
import aioimaplib
import aiostmtp

# Настройки файлов и окружения
KEYS_FILE = Path("keys.txt")
lock = asyncio.Lock()

# Конфигурация Gmail (переменные окружения)
GMAIL_USER = os.environ["GMAIL_USER"]          # Ваш адрес: example@gmail.com
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]  # ПАРОЛЬ ПРИЛОЖЕНИЯ (App Password)

# Настройки триггера
TRIGGER_SUBJECT = "ключ"  # Скрипт сработает, если в теме письма есть это слово


async def send_key_email(to_email: str, key: str):
    """Отправка email с ключом через SMTP."""
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = "Ваш игровой ключ! 🎮"
    msg.set_content(f"Привет!\n\nВот ваш запрошенный игровой ключ:\n{key}\n\nПриятной игры!")

    try:
        # Подключение к SMTP Gmail (порт 465 для SSL)
        async with aiostmtp.SMTP(hostname="://gmail.com", port=465, use_tls=True) as smtp:
            await smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            await smtp.send_message(msg)
        print(f"[✅] Ключ успешно отправлен на {to_email}")
    except Exception as e:
        print(f"[❌] Ошибка отправки письма на {to_email}: {e}")


async def get_and_pop_key() -> str | None:
    """Безопасное извлечение первого ключа из файла с удалением."""
    async with lock:
        if not KEYS_FILE.exists():
            return None
        
        keys = KEYS_FILE.read_text(encoding="utf-8").splitlines()
        if not keys:
            return None
        
        key = keys.pop(0)
        KEYS_FILE.write_text(
            "\n".join(keys) + ("\n" if keys else ""),
            encoding="utf-8"
        )
        return key


async def process_new_emails(imap_client):
    """Поиск писем и выдача ключей."""
    # Ищем НЕПРОЧИТАННЫЕ письма
    status, data = await imap_client.search('UNSEEN')
    if status != 'OK' or not data[0]:
        return

    msg_nums = data[0].split()
    for num in msg_nums:
        # Получаем заголовки письма (From и Subject)
        status, msg_data = await imap_client.fetch(num, '(BODY[HEADER.FIELDS (SUBJECT FROM)])')
        if status != 'OK':
            continue

        header_text = msg_data[0][1].decode('utf-8', errors='ignore')
        
        # Парсим тему и отправителя
        subject = ""
        from_email = ""
        for line in header_text.splitlines():
            if line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
            elif line.lower().startswith("from:"):
                # Базовый парсинг email из строки вида "Name <email@mail.com>"
                from_line = line.split(":", 1)[1].strip()
                if "<" in from_line and ">" in from_line:
                    from_email = from_line.split("<")[1].split(">")[0].strip()
                else:
                    from_email = from_line

        # Проверяем условие (триггер по теме письма)
        if TRIGGER_SUBJECT.lower() in subject.lower() and from_email:
            print(f"[📬] Получен запрос от {from_email} (Тема: {subject})")
            
            key = await get_and_pop_key()
            if key:
                await send_key_email(from_email, key)
                # Помечаем письмо как прочитанное, чтобы не обрабатывать повторно
                await imap_client.store(num, '+FLAGS (\\Seen)')
            else:
                print("[⚠️] Запрос отклонен: В файле keys.txt закончились ключи!")


async def main():
    print("[🚀] Скрипт проверки Gmail запущен и ожидает писем...")
    
    # Конфигурация SSL контекста
    ssl_context = ssl.create_default_context()
    
    while True:
        try:
            # Подключение к IMAP Gmail
            imap_client = aioimaplib.IMAP4_SSL(host="://googlemail.com", ssl_context=ssl_context)
            await imap_client.wait_hello()
            await imap_client.login(GMAIL_USER, GMAIL_PASSWORD)
            await imap_client.select('INBOX')

            # Каждые 10 секунд проверяем почту
            while True:
                await process_new_emails(imap_client)
                await asyncio.sleep(10)

        except Exception as e:
            print(f"[💥] Ошибка соединения или сессии: {e}. Переподключение через 15 секунд...")
            await asyncio.sleep(15)


if __name__ == "__main__":
    # Установка необходимых библиотек для асинхронного SMTP и IMAP:
    # pip install aioimaplib aiostmtp
    asyncio.run(main())
