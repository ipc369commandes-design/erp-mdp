from sqlalchemy import Column, Integer, String

from app.core.database import Base


class School(Base):

    __tablename__ = "schools"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    nom = Column(
        String,
        nullable=False,
        unique=True
    )

    ville = Column(
        String,
        nullable=True
    )

    actif = Column(
        Integer,
        nullable=False,
        default=1
    )