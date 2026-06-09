from pydantic import BaseModel


class SchoolYearCreate(BaseModel):
    libelle: str


class SchoolYearResponse(BaseModel):
    id: int
    libelle: str

    class Config:
        from_attributes = True