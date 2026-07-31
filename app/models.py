from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
