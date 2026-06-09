from sqlalchemy import Column, Integer, String

from app.core.database import Base


class SchoolList(Base):

    __tablename__ = "school_lists"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    school_id = Column(
        Integer,
        nullable=False
    )

    year_id = Column(
        Integer,
        nullable=False
    )

    classe = Column(
        String,
        nullable=False
    )

    titre = Column(
        String,
        nullable=True
    )

    slug = Column(
        String,
        nullable=False,
        unique=True
    )