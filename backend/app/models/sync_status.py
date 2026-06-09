from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime
from app.core.database import Base


class SyncStatus(Base):
    __tablename__ = "sync_status"

    code = Column(
        String,
        primary_key=True,
        nullable=False,
        index=True
    )

    status = Column(
        String,
        nullable=False,
        default="pending"  # pending, success, failed
    )

    last_sync = Column(
        DateTime,
        nullable=True,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    error_message = Column(
        Text,
        nullable=True,  # ✅ Peut être NULL
        default=None
    )
