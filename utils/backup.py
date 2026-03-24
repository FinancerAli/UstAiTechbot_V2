"""Send bot.db as document backup."""
import os
from aiogram import Bot
from aiogram.types import FSInputFile
from config import DB_PATH


async def send_backup(bot: Bot, admin_id: int):
    if not os.path.exists(DB_PATH):
        await bot.send_message(admin_id, "bot.db topilmadi!")
        return
    doc = FSInputFile(DB_PATH, filename="bot_backup.db")
    await bot.send_document(admin_id, doc, caption="💾 Bot database backup")
