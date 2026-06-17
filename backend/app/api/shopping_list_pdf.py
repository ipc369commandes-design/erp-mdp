"""
Endpoint pour générer le PDF des listes de fournitures scolaires depuis le panier (localStorage)
Design identique à la maquette HTML professionnelle
"""
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
from typing import List, Optional
import io as io_module
import base64
import urllib.request

from app.core.database import get_db

# ============= SCHEMAS =============
class CartItem(BaseModel):
    id: int
    code: str
    titre: str
    prix_vente: Optional[float] = None  # ✅ Sécurisé pour accepter des prix vides du localStorage
    qty: int
    image_url: Optional[str] = None

class GeneratePDFRequest(BaseModel):
    items: List[CartItem]

# Initialisation du routeur générique pour le panier d'achats
router = APIRouter()


def format_currency(value: Optional[float]) -> str:
    """Formater un montant numérique au format monétaire français (ex: 39 975 FCFA)"""
    val_float = float(value) if value is not None else 0.0
    return f"{val_float:,.0f}".replace(",", " ") + " FCFA"


# ============= ROUTE POST: GÉNÉRER PDF DEPUIS LE PANIER =============
@router.post("/generate-pdf")
def generate_pdf_from_cart(request: GeneratePDFRequest):
    """Générer un PDF depuis le panier (articles du localStorage) - Sécurisé"""
    
    try:
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
        
        # Ajustement sur 20 cm
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
        
        # Ajustement sur 20 cm
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

        # Ajustement sur 20 cm
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
        table_data = [
            [
                Paragraph("<b>N°</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>VISUEL</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>DÉSIGNATION</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>ISBN</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>QTÉ</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>PRIX</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9)),
                Paragraph("<b>CODE BARRE</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.white, leading=9))
            ]
        ]
        
        subtotal = 0
        
        for idx, item in enumerate(request.items, 1):
            # ✅ FIX : Sécurisation si le prix de vente d'un élément du panier est nul
            prix = item.prix_vente if item.prix_vente is not None else 0.0
            item_total = float(prix) * item.qty
            subtotal += item_total
            
            image_cell = Paragraph("📖", ParagraphStyle('img', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))
            
            if item.image_url:
                try:
                    if item.image_url.startswith('data:image'):
                        base64_str = item.image_url.split(',')[1]
                        image_data = base64.b64decode(base64_str)
                        image_io = io_module.BytesIO(image_data)
                        image_cell = RLImage(image_io, width=0.8*cm, height=1.1*cm)
                    elif item.image_url.startswith('http'):
                        try:
                            with urllib.request.urlopen(item.image_url, timeout=3) as response:
                                image_io = io_module.BytesIO(response.read())
                                image_cell = RLImage(image_io, width=0.8*cm, height=1.1*cm)
                        except Exception as e:
                            print(f"Erreur URL image: {e}")
                except Exception as e:
                    print(f"Erreur image: {e}")
            
            # ✅ FIX : Utilisation de 'item' au lieu de 'product' pour éviter le NameError
            table_data.append([
                Paragraph(str(idx), ParagraphStyle('TD', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)),
                image_cell,
                Paragraph(item.titre[:40] + "..." if len(item.titre) > 40 else item.titre, ParagraphStyle('TD', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT, leading=9)),
                Paragraph(item.code, ParagraphStyle('TD', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)),
                Paragraph(str(item.qty), ParagraphStyle('TD', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=9)),
                # ✅ FIX : Affichage dynamique du total de la ligne formaté (Prix unitaire x quantité)
                Paragraph(f"<b>{format_currency(item_total)}</b>", ParagraphStyle('TD', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT, leading=9, textColor=colors.HexColor('#001a70'), fontName='Helvetica-Bold')),
                Paragraph(item.code, ParagraphStyle('TD', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER, fontName='Courier', leading=8))
            ])
        
        if len(table_data) == 1:
            elements.append(Paragraph("Aucun article dans cette liste", styles['Normal']))
        else:
            # Ajustement sur 20 cm
            table = Table(
                table_data,
                repeatRows=1,
                colWidths=[1.0*cm, 1.5*cm, 10.5*cm, 2.5*cm, 1.0*cm, 2.0*cm, 1.5*cm]
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
                ('ALIGN', (6, 1), (6, -1), 'CENTER'),
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
            
            # Ajustement sur 20 cm
            occasion_table = Table(occasion_data, colWidths=[10.0*cm, 10.0*cm], rowHeights=[0.55*cm])
            occasion_table.setStyle(TableStyle([
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#d8def0')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(occasion_table)
            elements.append(Spacer(1, 0.15*cm))
            
            # ============= TOTALS SECTION (LIVE COMPUTED) =============
            discount = int(round(subtotal * 0.05))
            final_total = subtotal - discount
            
            totals_data = [
                [
                    Paragraph("<b>TOTAL AVANT REMISE</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_LEFT, textColor=colors.white, leading=11)),
                    Paragraph(f"<b>{format_currency(subtotal)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_RIGHT, textColor=colors.white, leading=11))
                ],
                [
                    Paragraph("<b>REMISE COMMERCIALE 5%</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_LEFT, textColor=colors.HexColor('#111'), leading=11)),
                    Paragraph(f"<b>- {format_currency(discount)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=TA_RIGHT, textColor=colors.HexColor('#111'), leading=11))
                ],
                [
                    Paragraph("<b>TOTAL TTC APRÈS REMISE</b>", ParagraphStyle('total_label', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_LEFT, textColor=colors.white, leading=12)),
                    Paragraph(f"<b>{format_currency(final_total)}</b>", ParagraphStyle('total_val', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_RIGHT, textColor=colors.white, leading=12))
                ]
            ]
            
            # Ajustement sur 20 cm
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
        
        # Ajustement sur 20 cm
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
        
        # Ajustement sur 20 cm
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
        
        # Retourner le PDF
        pdf_buffer.seek(0)
        
        return StreamingResponse(
            iter([pdf_buffer.getvalue()]),
            media_type='application/pdf',
            # ✅ FIX : Nom de fichier générique fixe pour le panier d'achats (pas de school_list.slug)
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