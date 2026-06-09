from pydantic import BaseModel
from typing import Optional


class SchoolListItemUpdate(BaseModel):
    quantite: int
    prix_force: Optional[float] = None