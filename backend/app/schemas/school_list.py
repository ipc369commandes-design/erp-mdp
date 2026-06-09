from pydantic import BaseModel




class SchoolListCreate(BaseModel):
    school_id: int
    year_id: int
    classe: str
    titre: str | None = None
    slug: str


class SchoolListResponse(BaseModel):
    id: int
    school_id: int
    year_id: int
    classe: str
    titre: str | None = None
    slug: str

    class Config:
        from_attributes = True
        

