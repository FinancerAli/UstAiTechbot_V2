import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Message, Update

import database as db
from config import BOT_TOKEN
from handlers import user, admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BlockCheckMiddleware:
    """Reject updates from blocked users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        user_id = None
        if isinstance(event, Update):
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id

        if user_id:
            db_user = await db.get_user(user_id)
            if db_user and db_user["is_blocked"]:
                if isinstance(event, Update) and event.message:
                    from locales import t
                    lang = db_user["language"] or "uz"
                    try:
                        await event.message.answer(t(lang, "blocked"))
                    except Exception:
                        pass
                return

        return await handler(event, data)


async def subscription_checker(bot: Bot):
    while True:
        try:
            subs = await db.get_expiring_subscriptions(3)
            for sub in subs:
                user_id = sub["user_id"]
                user = await db.get_user(user_id)
                lang = user["language"] if user and user["language"] else "uz"
                from locales import t
                try:
                    await bot.send_message(user_id, t(lang, "sub_expire_warning", days=3), parse_mode="HTML")
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"Subscription checker error: {e}")
            
        await asyncio.sleep(86400) # Check once a day

async def main():
    await db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(BlockCheckMiddleware())

    dp.include_router(admin.router)
    dp.include_router(user.router)

    logging.info("Bot ishga tushdi!")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(subscription_checker(bot))
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
