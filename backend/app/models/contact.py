from sqlalchemy import Column, Integer, String
from app.core.database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    # Nous mappons les attributs avec les noms de colonnes SQL d'origine pour assurer la compatibilité
    nom = Column("Nom", String, nullable=False)
    contacts = Column("Contacts", String, nullable=False, unique=True)