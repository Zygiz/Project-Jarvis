from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base

from sqlalchemy import Boolean, Column, DateTime, Integer, String

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    sender = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, default="user")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    task = Column(String, nullable=False)
    recipient = Column(String, nullable=False, index=True)
    due_at = Column(DateTime, nullable=False, index=True)
    sent = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)