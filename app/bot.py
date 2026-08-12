import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.auth import require_auth
from app.config import settings
from app.logging_config import setup_logging
from app.scheduler import send_due_reminders
from app.services import handle_message

setup_logging()
logger = logging.getLogger(__name__)


@require_auth
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("/start | user_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "Jarvis online.\n\nAsk me anything, or use /help to see commands."
    )


@require_auth
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("/help | user_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "Commands:\n"
        "/start - check I'm alive\n"
        "/help - this message\n\n"
        "Send me anything else and I'll answer it.\n"
        "Or set a reminder: \"remind me tomorrow at 09:00 to call the dentist\""
    )


@require_auth
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info("Message received | user_id=%s", user_id)

    reply = handle_message(text=update.message.text, sender=str(user_id))

    await update.message.reply_text(reply)


async def _start_scheduler(application: Application) -> None:
    """Start the reminder scheduler.

    Runs as a post_init hook because AsyncIOScheduler needs a running event
    loop to attach to, and the loop does not exist until the application
    starts. Calling scheduler.start() from the synchronous main() raises
    RuntimeError: no running event loop.
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_due_reminders, "interval", minutes=1)
    scheduler.start()
    logger.info("Reminder scheduler started | interval=1min")


def main() -> None:
    logger.info(
        "Jarvis bot starting up | allowed_users=%s", len(settings.allowed_user_ids)
    )

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_start_scheduler)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.run_polling()


if __name__ == "__main__":
    main()