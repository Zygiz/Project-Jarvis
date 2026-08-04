import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.config import settings
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with whatever the user sent."""
    text = update.message.text
    logger.info("Message received | user_id=%s", update.effective_user.id)
    await update.message.reply_text(f"You said: {text}")


def main() -> None:
    logger.info("Jarvis bot starting up (long-polling)")

    application = Application.builder().token(settings.telegram_bot_token).build()

    # Handle plain text messages, but not commands like /start
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # run_polling asks Telegram for new messages in a loop.
    # All connections go OUTWARD — no open ports needed.
    application.run_polling()


if __name__ == "__main__":
    main()