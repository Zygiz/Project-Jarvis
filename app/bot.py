from app.database import get_session
from app.models import Message
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def is_authorized(update: Update) -> bool:
    """Only allowlisted Telegram user IDs may use Jarvis."""
    return update.effective_user.id in settings.allowed_user_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        logger.warning("Unauthorized /start | user_id=%s", update.effective_user.id)
        return

    logger.info("/start | user_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "Jarvis online.\n\nSend me a message and I'll echo it back for now. "
        "Use /help to see what I can do."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        logger.warning("Unauthorized /help | user_id=%s", update.effective_user.id)
        return

    logger.info("/help | user_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "Commands:\n"
        "/start - check I'm alive\n"
        "/help - this message\n\n"
        "Anything else gets echoed back (LLM coming soon)."
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not is_authorized(update):
        logger.warning("Unauthorized access attempt | user_id=%s", user_id)
        return

    text = update.message.text
    logger.info("Message received | user_id=%s", user_id)

    with get_session() as session:
        session.add(Message(text=text, sender=str(user_id)))

    await update.message.reply_text(f"You said: {text}")


def main() -> None:
    logger.info(
        "Jarvis bot starting up | allowed_users=%s", len(settings.allowed_user_ids)
    )

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.run_polling()


if __name__ == "__main__":
    main()