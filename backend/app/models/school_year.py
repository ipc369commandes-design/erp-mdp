from sqlalchemy import Column, Integer, String

from app.core.database import Base


class SchoolYear(Base):

    __tablename__ = "school_years"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    libelle = Column(
        String,
        nullable=False,
        unique=True
    )