from pydantic import BaseModel


class SchoolListUpdate(BaseModel):
    classe: str
    titre: str