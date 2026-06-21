import csv
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.contact import Contact

router = APIRouter(
    prefix="/contacts",
    tags=["Contacts"]
)

def format_gabon_number(number: str) -> str:
    """Conserve la logique de formatage gabonais stricte de votre script Tkinter"""
    num_clean = "".join(filter(str.isdigit, number))
    if number.startswith("+241"):
        return number.replace("+", "")
    elif number.startswith("0"):
        return "241" + num_clean[1:]
    elif not num_clean.startswith("241"):
        return "241" + num_clean
    return num_clean

@router.post("")
def create_contact(nom: str, contacts: str, db: Session = Depends(get_db)):
    formatted_num = format_gabon_number(contacts)
    if len(formatted_num) != 12 or not formatted_num.startswith("241"):
        raise HTTPException(
            status_code=400, 
            detail="Numéro incorrect. Format attendu : 077448211 ou +241XXXXXXXXX."
        )
    
    # Vérification des doublons
    existing = db.query(Contact).filter(Contact.contacts == formatted_num).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce numéro de contact existe déjà.")

    obj = Contact(nom=nom, contacts=formatted_num)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "nom": obj.nom, "contacts": obj.contacts}

@router.get("")
def get_contacts(q: str = None, db: Session = Depends(get_db)):
    query = db.query(Contact)
    if q:
        search_filter = f"%{q}%"
        query = query.filter(
            (Contact.nom.ilike(search_filter)) | (Contact.contacts.like(search_filter))
        )
    results = query.all()
    return [{"id": c.id, "nom": c.nom, "contacts": c.contacts} for c in results]

@router.put("/{contact_id}")
def update_contact(contact_id: int, nom: str, contacts: str, db: Session = Depends(get_db)):
    obj = db.query(Contact).filter(Contact.id == contact_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Contact introuvable.")

    formatted_num = format_gabon_number(contacts)
    if len(formatted_num) != 12 or not formatted_num.startswith("241"):
        raise HTTPException(
            status_code=400, 
            detail="Numéro incorrect. Format attendu : 077448211 ou +241XXXXXXXXX."
        )

    # Vérification d'un doublon sur un autre contact
    duplicate = db.query(Contact).filter(Contact.contacts == formatted_num, Contact.id != contact_id).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Ce numéro est déjà attribué à un autre contact.")

    obj.nom = nom
    obj.contacts = formatted_num
    db.commit()
    return {"id": obj.id, "nom": obj.nom, "contacts": obj.contacts}

@router.delete("/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    obj = db.query(Contact).filter(Contact.id == contact_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Contact introuvable.")
    db.delete(obj)
    db.commit()
    return {"success": True}

@router.post("/import")
def import_contacts_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = file.file.read().decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        added = 0
        ignored = 0
        
        for row in reader:
            if not row or len(row) < 2:
                continue
            nom = row[0].strip()
            numero = row[1].strip()
            
            if not nom or not numero:
                continue
                
            formatted = format_gabon_number(numero)
            if len(formatted) == 12 and formatted.startswith("241"):
                exists = db.query(Contact).filter(Contact.contacts == formatted).first()
                if not exists:
                    obj = Contact(nom=nom, contacts=formatted)
                    db.add(obj)
                    added += 1
                else:
                    ignored += 1
            else:
                ignored += 1
                
        db.commit()
        return {"success": True, "added": added, "ignored": ignored}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur d'importation : {str(e)}")

@router.get("/export")
def export_contacts_csv(db: Session = Depends(get_db)):
    contacts = db.query(Contact).all()
    output = io.StringIO()
    writer = csv.writer(output)
    for c in contacts:
        writer.writerow([c.nom, c.contacts])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"}
    )