from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.school import School
from app.models.school_year import SchoolYear
from app.models.school_list import SchoolList
from app.models.school_list_item import SchoolListItem
from app.models.product import Product
from app.schemas.school_list_detail import SchoolListDetailResponse, SchoolListDetailItem

router = APIRouter(
    prefix="/public/school-lists",
    tags=["Public School Lists"]
)


@router.get("/schools")
def get_all_schools(db: Session = Depends(get_db)):
    """Récupérer la liste de tous les établissements actifs (PUBLIC)"""
    schools = db.query(School).filter(School.actif == 1).all()
    return [
        {
            "id": s.id,
            "nom": s.nom,
            "ville": s.ville
        }
        for s in schools
    ]


@router.get("/schools/{school_id}/years")
def get_school_years(
    school_id: int,
    db: Session = Depends(get_db)
):
    """Récupérer les années scolaires pour une école (PUBLIC)"""
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="École introuvable")
    
    years = db.query(SchoolYear).join(
        SchoolList, SchoolList.year_id == SchoolYear.id
    ).filter(
        SchoolList.school_id == school_id
    ).distinct().all()
    
    return [
        {
            "id": y.id,
            "libelle": y.libelle
        }
        for y in years
    ]


@router.get("/schools/{school_id}/years/{year_id}/classes")
def get_school_classes(
    school_id: int,
    year_id: int,
    db: Session = Depends(get_db)
):
    """Récupérer les classes disponibles pour une école et une année (PUBLIC)"""
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="École introuvable")
    
    year = db.query(SchoolYear).filter(SchoolYear.id == year_id).first()
    if not year:
        raise HTTPException(status_code=404, detail="Année scolaire introuvable")
    
    lists = db.query(SchoolList).filter(
        SchoolList.school_id == school_id,
        SchoolList.year_id == year_id
    ).all()
    
    return [
        {
            "id": sl.id,
            "classe": sl.classe,
            "titre": sl.titre,
            "slug": sl.slug
        }
        for sl in lists
    ]


@router.get("/schools/{school_id}/years/{year_id}/classes/{list_id}")
def get_school_list_details_public(
    school_id: int,
    year_id: int,
    list_id: int,
    db: Session = Depends(get_db)
):
    """Récupérer les détails d'une liste de fournitures (PUBLIC) - Requête optimisée"""
    school_list = db.query(SchoolList).filter(
        SchoolList.id == list_id,
        SchoolList.school_id == school_id,
        SchoolList.year_id == year_id
    ).first()
    
    if not school_list:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    
    # ✅ FIX : Requête jointe SQL pour ramener les articles et les produits associés en une seule fois
    items_with_products = db.query(SchoolListItem, Product).join(
        Product, SchoolListItem.product_id == Product.id
    ).filter(
        SchoolListItem.list_id == list_id
    ).all()
    
    result_items = []
    montant_total = 0
    
    for item, product in items_with_products:
        prix = item.prix_force if item.prix_force is not None else product.prix_vente
        total = float(prix) * item.quantite
        montant_total += total
        
        result_items.append(
            SchoolListDetailItem(
                product_id=int(product.id),
                code=product.code,
                titre=product.titre,
                image_url=product.image_url,
                prix_unitaire=float(prix),
                quantite=int(item.quantite),
                total=float(total)
            )
        )
    
    return SchoolListDetailResponse(
        id=int(school_list.id),
        classe=school_list.classe,
        titre=school_list.titre,
        montant_total=float(montant_total),
        items=result_items
    )


@router.get("/{slug}/public")
def get_school_list_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """Récupérer une liste de fournitures par son slug (PUBLIC) - Requête optimisée"""
    school_list = db.query(SchoolList).filter(SchoolList.slug == slug).first()
    if not school_list:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    
    # ✅ FIX : Jointure SQL pour éviter le problème d'I/O N+1
    items_with_products = db.query(SchoolListItem, Product).join(
        Product, SchoolListItem.product_id == Product.id
    ).filter(
        SchoolListItem.list_id == school_list.id
    ).all()
    
    school = db.query(School).filter(School.id == school_list.school_id).first()
    year = db.query(SchoolYear).filter(SchoolYear.id == school_list.year_id).first()
    
    result_items = []
    montant_total = 0
    
    for item, product in items_with_products:
        prix = item.prix_force if item.prix_force is not None else product.prix_vente
        total = float(prix) * item.quantite
        montant_total += total
        
        result_items.append({
            "product_id": int(product.id),
            "code": product.code,
            "titre": product.titre,
            "prix_unitaire": float(prix),
            "quantite": int(item.quantite),
            "total": float(total),
            "image_url": product.image_url
        })
    
    return {
        "id": int(school_list.id),
        "classe": school_list.classe,
        "titre": school_list.titre,
        "school": school.nom if school else "N/A",
        "year": year.libelle if year else "N/A",
        "montant_total": float(montant_total),
        "items": result_items
    }