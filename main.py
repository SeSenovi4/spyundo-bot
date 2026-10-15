
import os
import asyncio
import sqlite3

import aiohttp
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SESSION_STRING = os.environ["SESSION_STRING"]
NOTIFY_CHAT_ID = os.environ["NOTIFY_CHAT_ID"]

DATA_DIR = os.environ.get("DATA_DIR", "/tmp/spyundo")
os.makedirs(DATA_DIR, exist_ok=True)

db = sqlite3.connect(os.path.join(DATA_DIR, "messages.db"))
db.execute("""
CREATE TABLE IF NOT EXISTS messages (
    chat_id INTEGER,
    message_id INTEGER,
    chat_name TEXT,
    sender TEXT,
    message_text TEXT,
    PRIMARY KEY (chat_id, message_id)
)
""")
db.commit()

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

http = None


async def notify(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with http.post(
            url,
            json={
                "chat_id": NOTIFY_CHAT_ID,
                "text": text[:4000]
            }
        ) as response:
            if response.status != 200:
                print("Ошибка отправки уведомления:", await response.text())
    except Exception as e:
        print("Ошибка уведомления:", repr(e))


async def get_chat_name(event):
    try:
        chat = await event.get_chat()
        return (
            getattr(chat, "title", None)
            or getattr(chat, "first_name", None)
            or getattr(chat, "username", None)
            or str(event.chat_id)
        )
    except Exception:
        return str(event.chat_id)


async def get_sender_name(event):
    try:
        sender = await event.get_sender()
        if sender:
            name = " ".join(filter(None, [
                getattr(sender, "first_name", None),
                getattr(sender, "last_name", None)
            ]))
            return name or getattr(sender, "username", None) or str(sender.id)
    except Exception:
        pass
    return "Неизвестно"


def save_message(chat_id, message_id, chat_name, sender, text):
    db.execute(
        """
        INSERT OR REPLACE INTO messages
        (chat_id, message_id, chat_name, sender, message_text)
        VALUES (?, ?, ?, ?, ?)
        """,
        (chat_id, message_id, chat_name, sender, text or "[Нет текста]")
    )
    db.commit()


@client.on(events.NewMessage)
async def on_new_message(event):
    if event.chat_id is None:
        return

    chat_name = await get_chat_name(event)
    sender = await get_sender_name(event)

    save_message(
        event.chat_id,
        event.id,
        chat_name,
        sender,
        event.raw_text or "[Медиа или сообщение без текста]"
    )


@client.on(events.MessageEdited)
async def on_edited(event):
    if event.chat_id is None:
        return

    row = db.execute(
        """
        SELECT chat_name, sender, message_text
        FROM messages
        WHERE chat_id = ? AND message_id = ?
        """,
        (event.chat_id, event.id)
    ).fetchone()

    chat_name = await get_chat_name(event)
    sender = await get_sender_name(event)
    new_text = event.raw_text or "[Медиа или сообщение без текста]"

    if row and row[2] != new_text:
        await notify(
            "✏️ Сообщение отредактировано\n"
            f"Чат: {chat_name}\n"
            f"Автор: {sender}\n\n"
            f"Было:\n{row[2]}\n\n"
            f"Стало:\n{new_text}"
        )

    save_message(
        event.chat_id,
        event.id,
        chat_name,
        sender,
        new_text
    )


@client.on(events.MessageDeleted)
async def on_deleted(event):
    for message_id in event.deleted_ids:
        if event.chat_id is not None:
            rows = db.execute(
                """
                SELECT chat_id, chat_name, sender, message_text
                FROM messages
                WHERE chat_id = ? AND message_id = ?
                """,
                (event.chat_id, message_id)
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT chat_id, chat_name, sender, message_text
                FROM messages
                WHERE message_id = ?
                """,
                (message_id,)
            ).fetchall()

        if rows:
            for chat_id, chat_name, sender, text in rows:
                await notify(
                    "🗑 Обнаружено удаление сообщения\n"
                    f"Чат: {chat_name}\n"
                    f"Автор: {sender}\n"
                    f"ID: {message_id}\n\n"
                    f"Сохранённый текст:\n{text}"
                )
                db.execute(
                    "DELETE FROM messages WHERE chat_id = ? AND message_id = ?",
                    (chat_id, message_id)
                )
            db.commit()
        else:
            await notify(
                "🗑 Обнаружено удаление сообщения\n"
                f"ID: {message_id}\n"
                "Исходный текст не найден в сохранённых сообщениях."
            )


async def main():
    global http

    http = aiohttp.ClientSession()

    try:
        await client.connect()

        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram-сессия недействительна. "
                "Нужно заново создать SESSION_STRING."
            )

        me = await client.get_me()
        print(f"SpyUndo запущен. Аккаунт: {me.id}")

        await notify("✅ SpyUndo запущен и подключён к Telegram.")
        await client.run_until_disconnected()

    finally:
        await client.disconnect()
        await http.close()
        db.close()


asyncio.run(main())
