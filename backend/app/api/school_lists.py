from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.school import School
from app.models.school_year import SchoolYear
from app.models.school_list import SchoolList
from app.models.school_list_item import SchoolListItem
from app.models.product import Product

from app.schemas.school_list_detail import SchoolListDetailItem, SchoolListDetailResponse
from app.schemas.school_list_update import SchoolListUpdate
from app.schemas.school_list_item_update import SchoolListItemUpdate

from app.schemas.school import SchoolCreate, SchoolResponse
from app.schemas.school_year import SchoolYearCreate, SchoolYearResponse
from app.schemas.school_list import SchoolListCreate, SchoolListResponse
from app.schemas.school_list_item import SchoolListItemCreate, SchoolListItemResponse
from app.services.extractor_service import SchoolListExtractor

router = APIRouter(
    tags=["School Lists"]
)

@router.post("/schools", response_model=SchoolResponse)
def create_school(school: SchoolCreate, db: Session = Depends(get_db)):
    obj = School(nom=school.nom, ville=school.ville)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/schools", response_model=list[SchoolResponse])
def get_schools(db: Session = Depends(get_db)):
    return db.query(School).all()

@router.post("/school-years", response_model=SchoolYearResponse)
def create_school_year(year: SchoolYearCreate, db: Session = Depends(get_db)):
    obj = SchoolYear(libelle=year.libelle)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/school-years", response_model=list[SchoolYearResponse])
def get_school_years(db: Session = Depends(get_db)):
    return db.query(SchoolYear).all()

@router.post("/school-lists", response_model=SchoolListResponse)
def create_school_list(school_list: SchoolListCreate, db: Session = Depends(get_db)):
    obj = SchoolList(
        school_id=school_list.school_id,
        year_id=school_list.year_id,
        classe=school_list.classe,
        titre=school_list.titre,
        slug=school_list.slug
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/school-lists", response_model=list[SchoolListResponse])
def get_school_lists(db: Session = Depends(get_db)):
    return db.query(SchoolList).all()

@router.post("/school-list-items", response_model=SchoolListItemResponse)
def create_school_list_item(item: SchoolListItemCreate, db: Session = Depends(get_db)):
    obj = SchoolListItem(
        list_id=item.list_id,
        product_id=item.product_id,
        designation_libre=item.designation_libre,
        quantite=item.quantite,
        prix_force=item.prix_force
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/school-list-items/{list_id}", response_model=list[SchoolListItemResponse])
def get_school_list_items(list_id: int, db: Session = Depends(get_db)):
    return db.query(SchoolListItem).filter(SchoolListItem.list_id == list_id).all()

@router.get("/school-lists/{list_id}/details", response_model=SchoolListDetailResponse)
def get_school_list_details(list_id: int, db: Session = Depends(get_db)):
    school_list = db.query(SchoolList).filter(SchoolList.id == list_id).first()
    if not school_list:
        raise HTTPException(status_code=404, detail="Liste introuvable")

    # ✅ FIX : Requête jointe SQL pour éliminer l'I/O N+1 sur l'administration
    items_with_products = db.query(SchoolListItem, Product).join(
        Product, SchoolListItem.product_id == Product.id
    ).filter(
        SchoolListItem.list_id == list_id
    ).all()

    result_items = []
    montant_total = 0

    for item, product in items_with_products:
        prix = item.prix_force if item.prix_force is not None else product.prix_vente
        total = prix * item.quantite
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
    
@router.put("/school-lists/{list_id}", response_model=SchoolListResponse)
def update_school_list(list_id: int, data: SchoolListUpdate, db: Session = Depends(get_db)):
    obj = db.query(SchoolList).filter(SchoolList.id == list_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Liste introuvable")

    obj.classe = data.classe
    obj.titre = data.titre
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/school-lists/{list_id}")
def delete_school_list(list_id: int, db: Session = Depends(get_db)):
    obj = db.query(SchoolList).filter(SchoolList.id == list_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Liste introuvable")

    # Suppression des lignes d'articles liées pour éviter les données orphelines
    db.query(SchoolListItem).filter(SchoolListItem.list_id == list_id).delete()
    db.delete(obj)
    db.commit()
    return {"success": True}

@router.put("/school-list-items/{item_id}", response_model=SchoolListItemResponse)
def update_school_list_item(item_id: int, data: SchoolListItemUpdate, db: Session = Depends(get_db)):
    obj = db.query(SchoolListItem).filter(SchoolListItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Ligne introuvable")

    obj.quantite = data.quantite
    obj.prix_force = data.prix_force
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/school-list-items/{item_id}")
def delete_school_list_item(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(SchoolListItem).filter(SchoolListItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Ligne introuvable")

    db.delete(obj)
    db.commit()
    return {"success": True}

@router.delete("/schools/{id}")
def delete_school(id: int, db: Session = Depends(get_db)):
    obj = db.query(School).filter(School.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="École introuvable")
        
    # ✅ FIX : Suppression propre en cascade de toutes les listes et articles liés à cette école
    associated_lists = db.query(SchoolList).filter(SchoolList.school_id == id).all()
    for sl in associated_lists:
        db.query(SchoolListItem).filter(SchoolListItem.list_id == sl.id).delete()
        db.delete(sl)
        
    db.delete(obj)
    db.commit()
    return {"success": True}

@router.delete("/school-years/{id}")
def delete_year(id: int, db: Session = Depends(get_db)):
    obj = db.query(SchoolYear).filter(SchoolYear.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Année introuvable")
        
    # ✅ FIX : Suppression propre en cascade de toutes les listes et articles liés à cette année scolaire
    associated_lists = db.query(SchoolList).filter(SchoolList.year_id == id).all()
    for sl in associated_lists:
        db.query(SchoolListItem).filter(SchoolListItem.list_id == sl.id).delete()
        db.delete(sl)
        
    db.delete(obj)
    db.commit()
    return {"success": True}



@router.post("/school-lists/{list_id}/import-from-platform")
async def import_list_from_platform(list_id: int):
    """Déclencher l'extraction automatique de la page libre vers cette liste scolaire"""
    extractor = SchoolListExtractor(list_id=list_id)
    await extractor.extract_and_inject()
    return {"success": True, "message": "Extraction et valorisation terminées"}