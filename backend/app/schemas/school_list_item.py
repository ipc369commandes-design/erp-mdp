from pydantic import BaseModel


class SchoolListItemCreate(BaseModel):
    list_id: int
    product_id: int | None = None
    designation_libre: str | None = None
    quantite: int = 1
    prix_force: float | None = None


class SchoolListItemResponse(BaseModel):
    id: int
    list_id: int
    product_id: int | None = None
    designation_libre: str | None = None
    quantite: int
    prix_force: float | None = None

    class Config:
        from_attributes = True