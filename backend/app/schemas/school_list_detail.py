from pydantic import BaseModel


class SchoolListDetailItem(BaseModel):
    product_id: int
    code: str
    titre: str
    image_url: str | None = None

    prix_unitaire: float
    quantite: int
    total: float


class SchoolListDetailResponse(BaseModel):
    id: int
    classe: str
    titre: str | None = None
    montant_total: float
    items: list[SchoolListDetailItem]