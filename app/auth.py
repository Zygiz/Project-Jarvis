import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings

logger = logging.getLogger(__name__)


def require_auth(handler):
    """Decorator: silently ignore messages from non-allowlisted users.

    Wraps a Telegram handler so the auth check can't be forgotten.
    """

    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if user_id not in settings.allowed_user_ids:
            logger.warning("Unauthorized access attempt | user_id=%s", user_id)
            return  # silence — reveal nothing

        return await handler(update, context)

    return wrapper