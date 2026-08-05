import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.config import settings
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def is_authorized(update: Update) -> bool:
    """Only allowlisted Telegram user IDs may use Jarvis."""
    user_id = update.effective_user.id
    return user_id in settings.allowed_user_ids


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not is_authorized(update):
        logger.warning("Unauthorized access attempt | user_id=%s", user_id)
        return  # say nothing at all

    logger.info("Message received | user_id=%s", user_id)
    await update.message.reply_text(f"You said: {update.message.text}")


def main() -> None:
    logger.info(
        "Jarvis bot starting up | allowed_users=%s", len(settings.allowed_user_ids)
    )

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.run_polling()


if __name__ == "__main__":
    main()