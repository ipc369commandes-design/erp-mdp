from pydantic import BaseModel

class ContactCreate(BaseModel):
    nom: str
    contacts: str

class ContactResponse(BaseModel):
    id: int
    nom: str
    ville: str = "N/A" # facultatif, pour compatibilité
    
class SchoolListContactResponse(BaseModel):
    id: int
    school_id: int
    year_id: int
    classe: str
    titre: str
    slug: str