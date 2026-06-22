from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Any  # ✅ AJOUT : Import de Any pour le typage statique
import io as io_module
import base64
import urllib.request
import gc  # Pour forcer la libération de la RAM immédiatement
from PIL import Image as PILImage  # Pour compresser les images à la volée (Pillow est déjà requis par ReportLab)

# ✅ SÉCURITÉ CONTRE LES BOMBES DE DÉCOMPRESSION : max 10 mégapixels (évite de décoder des images géantes en RAM)
PILImage.MAX_IMAGE_PIXELS = 10000000

from app.core.database import get_db
from app.models.school_list import SchoolList
from app.models.school_list_item import SchoolListItem
from app.models.product import Product
from app.models.school import School
from app.models.school_year import SchoolYear

# ============= SCHEMAS =============
class CartItem(BaseModel):
    id: int
    code: str
    titre: str
    prix_vente: float
    qty: int
    image_url: Optional[str] = None

class GeneratePDFRequest(BaseModel):
    items: List[CartItem]
    discount_percent: Optional[float] = 0.0

# Initialisation du routeur générique sans préfixe
router = APIRouter()


def format_currency(value: float) -> str:
    """Formater un montant numérique au format monétaire français (ex: 39 975 FCFA)"""
    return f"{value:,.0f}".replace(",", " ") + " FCFA"


def compress_image_for_pdf(image_data_bytes: bytes) -> io_module.BytesIO:
    """
    ✅ SÉCURITÉ RAM (Render 512MB) :
    Compresse et redimensionne l'image à la volée sous forme de vignette (max 90x120).
    Utilise 'draft' de Pillow pour décoder à basse résolution directement (gain RAM/CPU).
    """
    try:
        in_buffer = io_module.BytesIO(image_data_bytes)
        with PILImage.open(in_buffer) as img:
            # ✅ ASTUCE DRAFT (JPEG uniquement) : Force le décodeur à ne décoder qu'une fraction de l'image
            try:
                img.draft("RGB", (90, 120))
            except Exception:
                pass  # Ne fait rien si le format ne supporte pas draft() (ex: PNG, WebP)
                
            # On convertit en RGB si l'image possède de la transparence pour la sauvegarder en JPEG léger
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Redimensionne proportionnellement vers un format vignette
            img.thumbnail((90, 120))
            
            out_buffer = io_module.BytesIO()
            img.save(out_buffer, format="JPEG", quality=75)
            out_buffer.seek(0)
            in_buffer.close()  # Libère le flux d'entrée immédiatement
            return out_buffer
    except Exception as e:
        print(f"⚠️ Impossible de compresser l'image, utilisation du flux brut : {e}")
        return io_module.BytesIO(image_data_bytes)


# ============= ROUTE POST: GÉNÉRER PDF DEPUIS LE PANIER =============
@router.post("/generate-pdf")
def generate_pdf_from_cart(request: GeneratePDFRequest):
    """Générer un PDF depuis le panier (articles du localStorage)"""
    
    try:
        pdf_buffer = io_module.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            topMargin=0.3*cm,
            bottomMargin=0.3*cm,
            leftMargin=0.4*cm,
            rightMargin=0.4*cm
        )
        
        styles = getSampleStyleSheet()
        elements = []
        
        # ============= HEADER SECTION =============
        logo_style = ParagraphStyle(
            'LogoStyle',
            parent=styles['Normal'],
            fontSize=24,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.HexColor('#001a70'),
            leading=22
        )
        
        contact_style = ParagraphStyle(
            'ContactStyle',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#111'),
            leading=10
        )
        
        shop_style = ParagraphStyle(
            'ShopStyle',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            leading=9
        )
        
        header_data = [
            [
                Paragraph(
                    "<font color='#001a70'><b>Maison de</b></font><br/>"
                    "<font color='#001a70'><b>la Presse</b></font><br/>"
                    "<font color='#f2b300'><b>Gabon</b></font><br/>"
                    "<font size=7 color='#001a70'><i>Lire, apprendre,<br/>réussir !</i></font>",
                    logo_style
                ),
                Paragraph(
                    "📞 011 72 21 31<br/>"
                    "📞 011 77 26 95<br/>"
                    "🟢 WhatsApp : 066 956 027<br/>"
                    "✉️ ipc369@yahoo.fr<br/>"
                    "🌐 www.maisondelapressegabon.com",
                    contact_style
                ),
                Paragraph(
                    "<b>2 MAGASINS</b><br/><br/>"
                    "📍 GLASS<br/>"
                    "📍 OKALA",
                    shop_style
                )
            ]
        ]
        
        header_table = Table(header_data, colWidths=[7.0*cm, 7.0*cm, 6.0*cm])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#001a70')),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('BORDER', (0, 0), (-1, -1), 2, colors.HexColor('#001a70')),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.25*cm))
        
        # ============= TOP BAR =============
        topbar_style = ParagraphStyle(
            'TopBarStyle',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.white,
            leading=11
        )
        
        topbar_data = [
            [
                Paragraph("📋 LISTE VALORISÉE", topbar_style),
                Paragraph("🛡️ ENGAGEMENTS", topbar_style),
                Paragraph("🎁 COUVERTURE GRATUITE", topbar_style)
            ]
        ]
        
        topbar_table = Table(topbar_data, colWidths=[7.0*cm, 6.0*cm, 7.0*cm], rowHeights=[0.65*cm])
        topbar_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, 0), 4),
        ]))
        elements.append(topbar_table)
        elements.append(Spacer(1, 0.2*cm))
        
        # ============= TITLE SECTION =============
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Normal'],
            fontSize=20,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.HexColor('#001a70'),
            leading=20
        )
        
        title_data = [
            [
                Paragraph(
                    "<font color='#001a70'><b>LISTE SCOLAIRE</b></font><br/>"
                    "<font color='#f2b300'><b>VALORISÉE</b></font>",
                    title_style
                ),
                Paragraph(
                    f"<b>PANIER EN COURS</b><br/>"
                    f"<font size=8>Maison de la Presse Gabon</font>",
                    ParagraphStyle(
                        'ClassStyle',
                        parent=styles['Normal'],
                        fontSize=14,
                        fontName='Helvetica-Bold',
                        alignment=TA_CENTER,
                        textColor=colors.white,
                        leading=15,
                        backColor=colors.HexColor('#001a70')
                    )
                )
            ]
        ]
        
        title_table = Table(title_data, colWidths=[13.0*cm, 7.0*cm], rowHeights=[1.1*cm])
        title_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#001a70')),
            ('PADDING', (0, 0), (0, 0), 6),
            ('PADDING', (1, 0), (1, 0), 8),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 0.2*cm))
        
        # ============= CLIENT SECTION =============
        client_header_style = ParagraphStyle(
            'ClientHeader',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.white,
            leading=10,
            backColor=colors.HexColor('#001a70')
        )

        client_content_style = ParagraphStyle(
            'ClientContent',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#111'),
            leading=9
        )

        client_data = [
            [
                Paragraph("CLIENT", client_header_style),
                Paragraph("CLIENT", client_header_style)
            ],
            [
                Paragraph("Nom & prénom : _______________________", client_content_style),
                Paragraph("Classe : _______________________", client_content_style)
            ],
            [
                Paragraph("Tél (WhatsApp) : _______________________", client_content_style),
                Paragraph("Observations : _______________________", client_content_style)
            ]
        ]

        client_table = Table(client_data, colWidths=[10.0*cm, 10.0*cm], rowHeights=[0.5*cm, 0.55*cm, 0.55*cm])
        client_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#d8def0')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(client_table)
        elements.append(Spacer(1, 0.15*cm))
        
        # ============= PRODUCTS TABLE =============
        # ✅ FIX : Colonne Code Barre retirée, colonne Prix Unitaire ajoutée.
        table_data: List[List[Any]] = [
            [
                Paragraph("<b>N°</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>VISUEL</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>DÉSIGNATION</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>ISBN</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>QTÉ</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>PRIX UNIT.</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>PRIX TOTAL</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9))
            ]
        ]
        
        subtotal = 0
        
        # ✅ OPTIMISATION RAM : Définition des styles réutilisables hors boucle
        style_cart_idx = ParagraphStyle('cart_idx', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)
        style_cart_titre = ParagraphStyle('cart_titre', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT, leading=9)
        style_cart_isbn = ParagraphStyle('cart_isbn', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)
        style_cart_qty = ParagraphStyle('cart_qty', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)
        style_cart_unit_prix = ParagraphStyle('cart_unit_prix', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT, leading=9, textColor=colors.HexColor('#475569'), fontName='Helvetica')
        style_cart_prix = ParagraphStyle('cart_prix', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT, leading=9, textColor=colors.HexColor('#001a70'), fontName='Helvetica-Bold')
        
        for idx, item in enumerate(request.items, 1):
            prix = item.prix_vente
            item_total = float(prix) * item.qty
            subtotal += item_total
            
            # ✅ FIX PYLANCE : Type Any pour supporter l'alternative de type au cours de la boucle
            image_cell: Any = Paragraph("📖", ParagraphStyle('img', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))
            
            if item.image_url:
                try:
                    image_data = None
                    if item.image_url.startswith('data:image'):
                        base64_str = item.image_url.split(',')[1]
                        # Sécurité Base64 : limite à 4 Mo pour éviter l'OOM
                        if len(base64_str) < 4 * 1024 * 1024:
                            image_data = base64.b64decode(base64_str)
                    elif item.image_url.startswith('http'):
                        try:
                            with urllib.request.urlopen(item.image_url, timeout=3) as response:
                                # Sécurité RAM : Max 3 Mo par image pour éviter l'explosion mémoire
                                image_data = response.read(3 * 1024 * 1024)
                        except Exception as e:
                            print(f"Erreur URL image: {e}")
                    
                    if image_data:
                        # Compression à la volée en vignette ultra-légère
                        compressed_io = compress_image_for_pdf(image_data)
                        image_cell = RLImage(compressed_io, width=0.8*cm, height=1.1*cm)
                        del image_data  # Libération de la RAM immédiatement après usage
                except Exception as e:
                    print(f"Erreur image: {e}")
            
            table_data.append([
                Paragraph(str(idx), style_cart_idx),
                image_cell,
                Paragraph(item.titre[:40] + "..." if len(item.titre) > 40 else item.titre, style_cart_titre),
                Paragraph(item.code, style_cart_isbn),
                Paragraph(str(item.qty), style_cart_qty),
                Paragraph(f"{float(prix):,.0f}", style_cart_unit_prix),
                Paragraph(f"<b>{item_total:,.0f}</b>", style_cart_prix)
            ])
        
        if len(table_data) == 1:
            elements.append(Paragraph("Aucun article dans cette liste", styles['Normal']))
        else:
            # colWidths réajusté pour conserver la largeur totale de 20.0 cm
            table = Table(
                table_data,
                repeatRows=1,
                colWidths=[1.0*cm, 1.5*cm, 10.0*cm, 2.5*cm, 1.0*cm, 2.0*cm, 2.0*cm]
            )
            
            table_style_list = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, 0), 2),
                ('LEADING', (0, 0), (-1, 0), 9),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('LEADING', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),
                ('ALIGN', (4, 1), (4, -1), 'CENTER'),
                ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
                ('ALIGN', (6, 1), (6, -1), 'RIGHT'),  # Prix Total aligné à DROITE
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('PADDING', (0, 1), (-1, -1), 2),
            ]
            
            for row_num in range(1, len(table_data)):
                bg_color = colors.white if row_num % 2 == 1 else colors.HexColor('#f8f8f8')
                table_style_list.append(('BACKGROUND', (0, row_num), (-1, row_num), bg_color))
            
            table.setStyle(TableStyle(table_style_list))
            elements.append(table)
            elements.append(Spacer(1, 0.15*cm))
            
            # ============= OCCASION SECTION =============
            occasion_style = ParagraphStyle(
                'OccasionStyle',
                parent=styles['Normal'],
                fontSize=8,
                fontName='Helvetica-Bold',
                alignment=TA_CENTER,
                textColor=colors.HexColor('#111'),
                leading=9
            )
            
            occasion_data = [
                [
                    Paragraph("📚 LIVRES SCOLAIRES D'OCCASION", occasion_style),
                    Paragraph("🌱 Donnez une seconde vie aux livres", occasion_style)
                ]
            ]
            
            occasion_table = Table(occasion_data, colWidths=[10.0*cm, 10.0*cm], rowHeights=[0.55*cm])
            occasion_table.setStyle(TableStyle([
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#d8def0')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(occasion_table)
            elements.append(Spacer(1, 0.15*cm))
            
            # ============= TOTALS SECTION (DYNAMIQUE) =============
            discount_percent = request.discount_percent if request.discount_percent is not None else 0.0
            discount = int(round(subtotal * (discount_percent / 100.0)))
            final_total = subtotal - discount

            discount_label = f"{int(discount_percent)}%" if discount_percent.is_integer() else f"{discount_percent}%"
            
            totals_data = [
                [
                    Paragraph("<b>TOTAL AVANT REMISE</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_LEFT, textColor=colors.white, leading=11)),
                    Paragraph(f"<b>{format_currency(subtotal)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_RIGHT, textColor=colors.white, leading=11))
                ],
                [
                    Paragraph(f"<b>REMISE COMMERCIALE {discount_label}</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#111'), leading=11)),
                    Paragraph(f"<b>- {format_currency(discount)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_RIGHT, textColor=colors.HexColor('#111'), leading=11))
                ],
                [
                    Paragraph("<b>TOTAL TTC APRÈS REMISE</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_LEFT, textColor=colors.white, leading=12)),
                    Paragraph(f"<b>{format_currency(final_total)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_RIGHT, textColor=colors.white, leading=12))
                ]
            ]
            
            totals_table = Table(totals_data, colWidths=[14.0*cm, 6.0*cm], rowHeights=[0.6*cm, 0.6*cm, 0.6*cm])
            totals_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fef08a')),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#854d0e')),
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f2b300')),
                ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#111')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(totals_table)
            elements.append(Spacer(1, 0.15*cm))
        
        # ============= PAYMENT SECTION =============
        payment_header_style = ParagraphStyle(
            'PaymentHeader',
            parent=styles['Normal'],
            fontSize=7,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.HexColor('#111'),
            leading=9
        )
        
        payment_data = [
            [
                Paragraph("<b>MOYENS DE PAIEMENT ACCEPTÉS</b><br/><br/><font color='red'><b>M4010</b></font>", payment_header_style),
                Paragraph("<b>PAIEMENT SÉCURISÉ</b><br/><br/>www.maisondelapressegabonairtel.com", payment_header_style),
                Paragraph("<b>CONDITIONS</b><br/><br/>Conditions générales de ventes disponibles en magasin", payment_header_style)
            ]
        ]
        
        payment_table = Table(payment_data, colWidths=[6.6*cm, 6.6*cm, 6.8*cm], rowHeights=[1.0*cm])
        payment_table.setStyle(TableStyle([
            ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#d8def0')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(payment_table)
        elements.append(Spacer(1, 0.15*cm))
        
        # ============= FOOTER =============
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=7,
            alignment=TA_CENTER,
            textColor=colors.white,
            leading=8
        )
        
        footer_data = [
            [
                Paragraph("La Maison de la Presse Gabon, partenaire privilégié de la réussite scolaire.", footer_style),
                Paragraph("Ce document est une liste valorisée et non un devis.", footer_style)
            ]
        ]
        
        footer_table = Table(footer_data, colWidths=[10.0*cm, 10.0*cm, 10.0*cm])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#001a70')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(footer_table)
        
        # Générer le PDF
        doc.build(elements)
        
        # ✅ NETTOYAGE EXPLICITE RAM : Références ReportLab détruites
        elements.clear()
        del elements
        gc.collect()
        
        # Retourner le PDF
        pdf_buffer.seek(0)
        
        # ✅ OPTIMISATION STREAM : StreamingResponse direct sans getvalue() pour éviter le double-buffer en mémoire
        return StreamingResponse(
            pdf_buffer,
            media_type='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=liste_scolaire.pdf'}
        )
        
    except Exception as e:
        print(f"Erreur PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération du PDF: {str(e)}"
        )


# ============= ROUTE GET: GÉNÉRER PDF DEPUIS UNE LISTE EXISTANTE =============
@router.get("/school-lists-pdf/{list_id}/pdf")
def generate_school_list_pdf(
    list_id: int,
    discount_percent: Optional[float] = 0.0,
    db: Session = Depends(get_db)
):
    """Générer un PDF de liste scolaire existante conforme à la maquette de valorisation"""
    
    try:
        # Récupérer la liste
        school_list = db.query(SchoolList).filter(SchoolList.id == list_id).first()
        if not school_list:
            raise HTTPException(status_code=404, detail="Liste introuvable")
        
        # Récupérer l'école et l'année
        school = db.query(School).filter(School.id == school_list.school_id).first()
        year = db.query(SchoolYear).filter(SchoolYear.id == school_list.year_id).first()
        
        # Récupération optimisée avec jointure pour éviter le N+1
        items_with_products = db.query(SchoolListItem, Product).join(
            Product, SchoolListItem.product_id == Product.id
        ).filter(
            SchoolListItem.list_id == list_id
        ).all()
        
        # Créer le PDF
        pdf_buffer = io_module.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            topMargin=0.3*cm,
            bottomMargin=0.3*cm,
            leftMargin=0.4*cm,
            rightMargin=0.4*cm
        )
        
        styles = getSampleStyleSheet()
        elements = []
        
        # ============= HEADER SECTION =============
        logo_style = ParagraphStyle(
            'LogoStyle',
            parent=styles['Normal'],
            fontSize=24,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.HexColor('#001a70'),
            leading=22
        )
        
        contact_style = ParagraphStyle(
            'ContactStyle',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#111'),
            leading=10
        )
        
        shop_style = ParagraphStyle(
            'ShopStyle',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            leading=9
        )
        
        school_name = school.nom if school else "N/A"
        
        header_data = [
            [
                Paragraph(
                    "<font color='#001a70'><b>Maison de</b></font><br/>"
                    "<font color='#001a70'><b>la Presse</b></font><br/>"
                    "<font color='#f2b300'><b>Gabon</b></font><br/>"
                    "<font size=7 color='#001a70'><i>Lire, apprendre,<br/>réussir !</i></font>",
                    logo_style
                ),
                Paragraph(
                    "📞 011 72 21 31<br/>"
                    "📞 011 77 26 95<br/>"
                    "🟢 WhatsApp : 066 956 027<br/>"
                    "✉️ ipc369@yahoo.fr<br/>"
                    "🌐 www.maisondelapressegabon.com",
                    contact_style
                ),
                Paragraph(
                    "<b>2 MAGASINS</b><br/><br/>"
                    "📍 GLASS<br/>"
                    "📍 OKALA",
                    shop_style
                )
            ]
        ]
        
        # Ajustement sur 20 cm
        header_table = Table(header_data, colWidths=[7.0*cm, 7.0*cm, 6.0*cm])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#001a70')),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('BORDER', (0, 0), (-1, -1), 2, colors.HexColor('#001a70')),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.25*cm))
        
        # ============= TOP BAR =============
        topbar_style = ParagraphStyle(
            'TopBarStyle',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.white,
            leading=11
        )
        
        topbar_data = [
            [
                Paragraph("📋 LISTE VALORISÉE", topbar_style),
                Paragraph("🛡️ ENGAGEMENTS", topbar_style),
                Paragraph("🎁 COUVERTURE GRATUITE", topbar_style)
            ]
        ]
        
        topbar_table = Table(topbar_data, colWidths=[7.0*cm, 6.0*cm, 7.0*cm], rowHeights=[0.65*cm])
        topbar_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, 0), 4),
        ]))
        elements.append(topbar_table)
        elements.append(Spacer(1, 0.2*cm))
        
        # ============= TITLE SECTION =============
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Normal'],
            fontSize=20,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.HexColor('#001a70'),
            leading=20
        )
        
        class_name = school_list.classe if school_list else "N/A"
        
        title_data = [
            [
                Paragraph(
                    "<font color='#001a70'><b>LISTE SCOLAIRE</b></font><br/>"
                    "<font color='#f2b300'><b>VALORISÉE</b></font>",
                    title_style
                ),
                Paragraph(
                    f"<b>{class_name}</b><br/>"
                    f"<font size=8>{school_name}</font>",
                    ParagraphStyle(
                        'ClassStyle',
                        parent=styles['Normal'],
                        fontSize=14,
                        fontName='Helvetica-Bold',
                        alignment=TA_CENTER,
                        textColor=colors.white,
                        leading=15,
                        backColor=colors.HexColor('#001a70')
                    )
                )
            ]
        ]
        
        title_table = Table(title_data, colWidths=[13.0*cm, 7.0*cm], rowHeights=[1.1*cm])
        title_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#001a70')),
            ('PADDING', (0, 0), (0, 0), 6),
            ('PADDING', (1, 0), (1, 0), 8),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 0.2*cm))
        
        # ============= CLIENT SECTION =============
        client_header_style = ParagraphStyle(
            'ClientHeader',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.white,
            leading=10,
            backColor=colors.HexColor('#001a70')
        )

        client_content_style = ParagraphStyle(
            'ClientContent',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#111'),
            leading=9
        )

        client_data = [
            [
                Paragraph("CLIENT", client_header_style),
                Paragraph("CLIENT", client_header_style)
            ],
            [
                Paragraph("Nom & prénom : _______________________", client_content_style),
                Paragraph(f"Classe : {class_name}", client_content_style)
            ],
            [
                Paragraph("Tél (WhatsApp) : _______________________", client_content_style),
                Paragraph("Observations : _______________________", client_content_style)
            ]
        ]

        client_table = Table(client_data, colWidths=[10.0*cm, 10.0*cm], rowHeights=[0.5*cm, 0.55*cm, 0.55*cm])
        client_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#d8def0')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(client_table)
        elements.append(Spacer(1, 0.15*cm))
        
        # ============= PRODUCTS TABLE =============
        # ✅ FIX : Colonne Code Barre retirée, colonne Prix Unitaire ajoutée.
        table_data: List[List[Any]] = [
            [
                Paragraph("<b>N°</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>VISUEL</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>DÉSIGNATION</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>ISBN/EAN</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>QTÉ</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>PRIX UNIT.</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>PRIX TOTAL</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9))
            ]
        ]
        
        subtotal = 0
        
        # ✅ OPTIMISATION RAM : Définition des styles réutilisables hors boucle
        style_list_idx = ParagraphStyle('list_idx', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)
        style_list_titre = ParagraphStyle('list_titre', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT, leading=9)
        style_list_isbn = ParagraphStyle('list_isbn', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)
        style_list_qty = ParagraphStyle('list_qty', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)
        style_list_unit_prix = ParagraphStyle('list_unit_prix', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT, leading=9, textColor=colors.HexColor('#475569'), fontName='Helvetica')
        style_list_prix = ParagraphStyle('list_prix', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT, leading=9, textColor=colors.HexColor('#001a70'), fontName='Helvetica-Bold')
        
        for idx, (item, product) in enumerate(items_with_products, 1):
            prix = item.prix_force if item.prix_force else product.prix_vente
            item_total = float(prix) * item.quantite
            subtotal += item_total
            
            # ✅ FIX PYLANCE : Type Any pour supporter l'alternative de type au cours de la boucle
            image_cell: Any = Paragraph("📖", ParagraphStyle('img', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))
            
            if product.image_url:
                try:
                    image_data = None
                    if product.image_url.startswith('data:image'):
                        base64_str = product.image_url.split(',')[1]
                        # Sécurité Base64 : limite à 4 Mo pour éviter l'OOM
                        if len(base64_str) < 4 * 1024 * 1024:
                            image_data = base64.b64decode(base64_str)
                    elif product.image_url.startswith('http'):
                        try:
                            with urllib.request.urlopen(product.image_url, timeout=3) as response:
                                # Sécurité RAM : Max 3 Mo par image pour éviter le débordement
                                image_data = response.read(3 * 1024 * 1024)
                        except Exception as e:
                            print(f"⚠️ Image URL skip (Timeout ou indisponible): {e}")
                    
                    if image_data:
                        # Compression à la volée en vignette ultra-légère
                        compressed_io = compress_image_for_pdf(image_data)
                        image_cell = RLImage(compressed_io, width=0.8*cm, height=1.1*cm)
                        del image_data  # Libération de la RAM immédiatement après usage
                except Exception as e:
                    print(f"⚠️ Erreur décodage image: {e}")
            
            table_data.append([
                Paragraph(str(idx), style_list_idx),
                image_cell,
                Paragraph(product.titre[:40] + "..." if len(product.titre) > 40 else product.titre, style_list_titre),
                Paragraph(product.code, style_list_isbn),
                Paragraph(str(item.quantite), style_list_qty),
                Paragraph(f"{float(prix):,.0f}", style_list_unit_prix),
                Paragraph(f"<b>{format_currency(item_total)}</b>", style_list_prix)
            ])
        
        if len(table_data) == 1:
            elements.append(Paragraph("Aucun article dans cette liste", styles['Normal']))
        else:
            # colWidths réajusté pour conserver la largeur totale de 20.0 cm
            table = Table(
                table_data,
                repeatRows=1,
                colWidths=[1.0*cm, 1.5*cm, 10.0*cm, 2.5*cm, 1.0*cm, 2.0*cm, 2.0*cm]
            )
            
            table_style_list = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, 0), 2),
                ('LEADING', (0, 0), (-1, 0), 9),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('LEADING', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),
                ('ALIGN', (4, 1), (4, -1), 'CENTER'),
                ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
                ('ALIGN', (6, 1), (6, -1), 'RIGHT'),  # Prix Total aligné à DROITE
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('PADDING', (0, 1), (-1, -1), 2),
            ]
            
            for row_num in range(1, len(table_data)):
                bg_color = colors.white if row_num % 2 == 1 else colors.HexColor('#f8f8f8')
                table_style_list.append(('BACKGROUND', (0, row_num), (-1, row_num), bg_color))
            
            table.setStyle(TableStyle(table_style_list))
            elements.append(table)
            elements.append(Spacer(1, 0.15*cm))
            
            # ============= OCCASION SECTION =============
            occasion_style = ParagraphStyle(
                'OccasionStyle',
                parent=styles['Normal'],
                fontSize=8,
                fontName='Helvetica-Bold',
                alignment=TA_CENTER,
                textColor=colors.HexColor('#111'),
                leading=9
            )
            
            occasion_data = [
                [
                    Paragraph("📚 LIVRES SCOLAIRES D'OCCASION", occasion_style),
                    Paragraph("🌱 Donnez une seconde vie aux livres", occasion_style)
                ]
            ]
            
            occasion_table = Table(occasion_data, colWidths=[10.0*cm, 10.0*cm], rowHeights=[0.55*cm])
            occasion_table.setStyle(TableStyle([
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#d8def0')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(occasion_table)
            elements.append(Spacer(1, 0.15*cm))
            
            # ============= TOTALS SECTION (DYNAMIQUE) =============
            pct = discount_percent if discount_percent is not None else 0.0
            discount = int(round(subtotal * (pct / 100.0)))
            final_total = subtotal - discount

            discount_label = f"{int(pct)}%" if pct.is_integer() else f"{pct}%"
            
            totals_data = [
                [
                    Paragraph("<b>TOTAL AVANT REMISE</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_LEFT, textColor=colors.white, leading=11)),
                    Paragraph(f"<b>{format_currency(subtotal)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_RIGHT, textColor=colors.white, leading=11))
                ],
                [
                    Paragraph(f"<b>REMISE COMMERCIALE {discount_label}</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#111'), leading=11)),
                    Paragraph(f"<b>- {format_currency(discount)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_RIGHT, textColor=colors.HexColor('#111'), leading=11))
                ],
                [
                    Paragraph("<b>TOTAL TTC APRÈS REMISE</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_LEFT, textColor=colors.white, leading=12)),
                    Paragraph(f"<b>{format_currency(final_total)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_RIGHT, textColor=colors.white, leading=12))
                ]
            ]
            
            totals_table = Table(totals_data, colWidths=[14.0*cm, 6.0*cm], rowHeights=[0.6*cm, 0.6*cm, 0.6*cm])
            totals_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001a70')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fef08a')),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#854d0e')),
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f2b300')),
                ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#111')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(totals_table)
            elements.append(Spacer(1, 0.15*cm))
        
        # ============= PAYMENT SECTION =============
        payment_header_style = ParagraphStyle(
            'PaymentHeader',
            parent=styles['Normal'],
            fontSize=7,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.HexColor('#111'),
            leading=9
        )
        
        payment_data = [
            [
                Paragraph("<b>MOYENS DE PAIEMENT ACCEPTÉS</b><br/><br/><font color='red'><b>M4010</b></font>", payment_header_style),
                Paragraph("<b>PAIEMENT SÉCURISÉ</b><br/><br/>www.maisondelapressegabonairtel.com", payment_header_style),
                Paragraph("<b>CONDITIONS</b><br/><br/>Conditions générales de ventes disponibles en magasin", payment_header_style)
            ]
        ]
        
        payment_table = Table(payment_data, colWidths=[6.6*cm, 6.6*cm, 6.8*cm], rowHeights=[1.0*cm])
        payment_table.setStyle(TableStyle([
            ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#d8def0')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(payment_table)
        elements.append(Spacer(1, 0.15*cm))
        
        # ============= FOOTER =============
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=7,
            alignment=TA_CENTER,
            textColor=colors.white,
            leading=8
        )
        
        footer_data = [
            [
                Paragraph("La Maison de la Presse Gabon, partenaire privilégié de la réussite scolaire.", footer_style),
                Paragraph("Ce document est une liste valorisée et non un devis.", footer_style)
            ]
        ]
        
        footer_table = Table(footer_data, colWidths=[10.0*cm, 10.0*cm], rowHeights=[0.55*cm])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#001a70')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(footer_table)
        
        # Générer le PDF
        doc.build(elements)
        
        # ✅ NETTOYAGE EXPLICITE RAM : Références ReportLab détruites
        elements.clear()
        del elements
        gc.collect()
        
        # Retourner le PDF
        pdf_buffer.seek(0)
        
        # ✅ OPTIMISATION STREAM : StreamingResponse direct sans getvalue() pour éviter le double-buffer en mémoire
        return StreamingResponse(
            pdf_buffer,
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=liste_{school_list.slug}.pdf'}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération du PDF: {str(e)}"
        )