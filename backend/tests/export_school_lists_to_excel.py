import os
import re
import asyncio
from typing import Optional
from openpyxl import Workbook

from app.core.playwright_manager import PlaywrightManager
from app.services.auth import AuthManager

# Configuration des expressions régulières pour nettoyer les données
EAN_REGEX = re.compile(r'\b(97[89][0-9]{10}|[0-9]{13})\b')
QTY_REGEX = re.compile(r'\b([1-9]|[1-9][0-9])\b')

def extract_ean(text: str) -> Optional[str]:
    match = EAN_REGEX.search(text)
    return match.group(1) if match else None

def extract_quantity(text: str) -> int:
    match = QTY_REGEX.search(text.strip())
    return int(match.group(1)) if match else 1

async def main():
    # URL de départ (Index de l'établissement)
    start_url = "https://www.maisondelapressegabon.com/gestion/pages_libres.php?animation=1&ssh_id=12500"
    print("🚀 Démarrage du script d'extraction autonome multi-pages sécurisé...")

    auth = AuthManager()
    await auth.init_session()
    page = auth.page

    if not page:
        print("❌ Échec de l'initialisation du navigateur.")
        await auth.close()
        return

    try:
        # Étape 1 : Connexion à pages_libres.php pour l'école
        print(f"📡 Connexion à l'établissement : {start_url}...")
        await page.goto(start_url, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Trouver le lien vers blocLibre_list.php
        bloc_link = await page.locator("a[href*='blocLibre_list.php?']").first.get_attribute("href")
        if not bloc_link:
            print("❌ Impossible de trouver le lien vers blocLibre_list.php.")
            return

        intermediate_url = f"https://www.maisondelapressegabon.com/gestion/{bloc_link}"
        
        # Étape 2 : Connexion à blocLibre_list.php pour lister les classes
        print(f"📡 Connexion au gestionnaire des blocs : {intermediate_url}...")
        await page.goto(intermediate_url, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Trouver tous les liens d'édition de tableaux (table_modif.php)
        links = await page.locator("a[href*='table_modif.php?']").all()
        classes_urls = []
        for link in links:
            href = await link.get_attribute("href")
            text = await link.inner_text()
            if href:
                full_url = f"https://www.maisondelapressegabon.com/gestion/{href}"
                if full_url not in [u[0] for u in classes_urls]:
                    classes_urls.append((full_url, text.strip() or "Classe"))

        print(f"🔗 {len(classes_urls)} classes découvertes (pages table_modif.php) !")

        # Étape 3 : Initialisation Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Données Extraites"
        ws.append(["Maquette / Liste", "ISBN / EAN", "Désignation", "Quantité", "Prix de Vente"])

        # Étape 4 : Scraper chaque classe de manière sécurisée
        for idx, (url, class_name) in enumerate(classes_urls, 1):
            print(f"\n🕷️ ({idx}/{len(classes_urls)}) Navigation vers la classe : '{class_name}'...")
            try:
                # ✅ FIX : Syntaxe d'appel corrigée ici sans mot-clé orphelin 'page_'
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                # Extraire automatiquement le vrai nom de la classe depuis le grand titre de la page (h1, h2, h3)
                header_text = ""
                h1_locator = page.locator("h1, h2, h3, .title, .main-title").first
                if await h1_locator.count() > 0:
                    header_text = await h1_locator.inner_text()
                    # Nettoyage cosmétique du titre
                    header_text = header_text.replace("Modification du tableau", "").replace("-", "").strip()
                
                document_name = header_text or class_name or "Classe"
                print(f"   -> Classe identifiée : '{document_name}'")

                rows = await page.locator("table tr").all()
                page_inserted = 0

                for row in rows:
                    tds = await row.locator("td").all()
                    if not tds or len(tds) < 3:
                        continue

                    # Extraction intelligente de la valeur des cellules (Texte OU Valeur de l'input de formulaire)
                    cells_values = []
                    for td in tds:
                        inputs = await td.locator("input").all()
                        if inputs:
                            input_type = await inputs[0].get_attribute("type") or "text"
                            # Ignorer les boutons et cases à cocher de suppression d'origine
                            if input_type.lower() not in ["submit", "button", "checkbox"]:
                                val = await inputs[0].get_attribute("value")
                                cells_values.append(val or "")
                            else:
                                cells_values.append("")
                        else:
                            text = await td.inner_text()
                            cells_values.append(text.strip())

                    # Traiter les valeurs extraites
                    isbn = None
                    qty = 1
                    title = ""
                    price = ""

                    for val_clean in cells_values:
                        if not val_clean:
                            continue
                        
                        # A. Détecter l'ISBN à 13 chiffres
                        detected_ean = extract_ean(val_clean)
                        if detected_ean:
                            isbn = detected_ean
                            continue
                        
                        # B. Détecter la quantité (généralement un petit entier isolé)
                        if len(val_clean) <= 3 and val_clean.isdigit():
                            qty = extract_quantity(val_clean)
                            continue
                        
                        # C. Détecter le prix de vente
                        if ("fcfa" in val_clean.lower() or "f" in val_clean.lower() or val_clean.replace(" ", "").isdigit()) and len(val_clean) > 3:
                            price = val_clean.replace("FCFA", "").replace("F", "").replace(" ", "").strip()
                            continue
                        
                        # D. Détecter le titre (chaîne textuelle de désignation)
                        if len(val_clean) > 5 and not val_clean.replace(" ", "").isdigit():
                            title = val_clean

                    if isbn:
                        price_val = int(price) if price.isdigit() else price
                        ws.append([document_name, isbn, title, qty, price_val])
                        page_inserted += 1

                print(f"   -> ✅ {page_inserted} articles écrits pour '{document_name}'.")

            except Exception as e:
                print(f"   ❌ Erreur d'extraction sur cette classe : {e}")

        # Étape 5 : Sauvegarde du fichier Excel
        excel_filename = "export_listes_gabon.xlsx"
        wb.save(excel_filename)
        print(f"\n🏁 SCRIPT TERMINÉ AVEC SUCCÈS ! Fichier enregistré sous '{excel_filename}'")

    except Exception as e:
        print(f"❌ Erreur critique : {e}")
    finally:
        await auth.close()

if __name__ == "__main__":
    asyncio.run(main())