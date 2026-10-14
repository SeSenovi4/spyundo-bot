
import os
import asyncio
from telethon import TelegramClient, events

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

client = TelegramClient("spyundo_session", API_ID, API_HASH)

@client.on(events.NewMessage)
async def on_new_message(event):
    if event.out:
        return
    sender = await event.get_sender()
    name = getattr(sender, "first_name", None) or getattr(sender, "title", "Неизвестно")
    text = event.raw_text or "[Медиа или сообщение без текста]"
    print(f"Новое сообщение от {name}: {text}")

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("SpyUndo запущен")
    await client.run_until_disconnected()

asyncio.run(main())
