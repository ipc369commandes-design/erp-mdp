from pydantic import BaseModel


class SchoolCreate(BaseModel):
    nom: str
    ville: str | None = None


class SchoolResponse(BaseModel):
    id: int
    nom: str
    ville: str | None = None
    actif: int

    class Config:
        from_attributes = True