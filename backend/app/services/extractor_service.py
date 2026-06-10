import os
import sys
import re
import asyncio
from typing import Optional
from sqlalchemy.orm import Session

from app.core.playwright_manager import PlaywrightManager
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.school_list_item import SchoolListItem
from app.services.auth import AuthManager  # ✅ Réutilisation de l'AuthManager sécurisé

class SchoolListExtractor:
    def __init__(self, list_id: int):
        self.list_id = list_id
        self.target_url = "https://www.maisondelapressegabon.com/gestion/pages_libres.php"

    def clean_ean(self, text: str) -> Optional[str]:
        """Extraire un EAN/ISBN à 13 chiffres à l'aide d'une regex"""
        match = re.search(r'\b(97[89][0-9]{10}|[0-9]{13})\b', text)
        return match.group(1) if match else None

    def clean_quantity(self, text: str) -> int:
        """Extraire et nettoyer la quantité numérique"""
        match = re.search(r'\b([1-9]|[1-9][0-9])\b', text.strip())
        return int(match.group(1)) if match else 1

    async def extract_and_inject(self):
        """Naviguer, extraire les articles de la page libre et les injecter de façon sécurisée"""
        print("🔄 Démarrage de l'extraction de la liste...")
        
        # ✅ Utilisation de l'AuthManager pour garantir une session valide et connectée
        auth = AuthManager()
        await auth.init_session()
        
        page = auth.page
        if not page:
            print("❌ Échec : Impossible d'initialiser la page du navigateur.")
            await auth.close()
            return

        try:
            print(f"📡 Navigation vers {self.target_url}...")
            await page.goto(self.target_url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # ✅ DEBUG : Afficher l'URL et le titre réels pour détecter les redirections d'expiration
            current_url = page.url
            page_title = await page.title()
            print(f"📍 URL actuelle : {current_url}")
            print(f"📝 Titre de la page : {page_title}")

            if "login" in current_url.lower() or "connexion" in current_url.lower():
                print("❌ Échec : Vous avez été redirigé vers l'écran de connexion.")
                print("   Vérifiez vos identifiants USERNAME et PASSWORD dans auth.py.")
                return

            # Extraire toutes les lignes de tableaux (<tr>) de la page
            rows = await page.locator("table tr").all()
            print(f"📊 {len(rows)} lignes de tableau détectées sur la page.")

            if len(rows) == 0:
                print("⚠️ Aucun tableau détecté. Est-ce que la page libre est vide ou utilise un autre format ?")
                # Prendre une capture d'écran de débug pour voir ce qui s'affiche réellement
                await page.screenshot(path="debug_pages_libres.png", full_page=True)
                print("📷 Capture d'écran de débug enregistrée sous 'debug_pages_libres.png'")
                return

            db: Session = SessionLocal()
            inserted_count = 0
            skipped_count = 0

            for idx, row in enumerate(rows):
                cells = await row.locator("td").all_text_contents()
                
                if not cells or len(cells) < 3:
                    continue

                isbn = None
                qty = 1
                title = ""

                for cell in cells:
                    cell_clean = cell.strip()
                    detected_ean = self.clean_ean(cell_clean)
                    if detected_ean:
                        isbn = detected_ean
                        continue
                    
                    if len(cell_clean) <= 3 and cell_clean.isdigit():
                        qty = self.clean_quantity(cell_clean)
                        continue
                    
                    if len(cell_clean) > 5 and not cell_clean.isdigit():
                        title = cell_clean

                if isbn:
                    product = db.query(Product).filter(Product.code == isbn).first()
                    
                    if product:
                        existing_item = db.query(SchoolListItem).filter(
                            SchoolListItem.list_id == self.list_id,
                            SchoolListItem.product_id == product.id
                        ).first()

                        if not existing_item:
                            new_item = SchoolListItem(
                                list_id=self.list_id,
                                product_id=product.id,
                                quantite=qty,
                                designation_libre=product.titre
                            )
                            db.add(new_item)
                            inserted_count += 1
                            print(f"✅ Injecté : {product.titre[:30]} (ISBN: {isbn}, Qté: {qty})")
                        else:
                            skipped_count += 1
                    else:
                        print(f"⚠️ Produit introuvable dans le catalogue local (EAN: {isbn} | {title[:30]})")
                        skipped_count += 1

            db.commit()
            db.close()
            
            print(f"\n🏁 Extraction terminée !")
            print(f"   • {inserted_count} articles importés et valorisés")
            print(f"   • {skipped_count} articles ignorés")

        except Exception as e:
            print(f"❌ Erreur lors de l'extraction : {e}")
        finally:
            await auth.close()