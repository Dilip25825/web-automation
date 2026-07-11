# licensing/utils.py (Nayi file bana kar ye code dalein)

import os
import io
from datetime import datetime
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# ON ERROR HANDLING: Data process ko safe rakhne ke liye functional logic block
def generate_pacs_invoice_pdf(request, client,customAmount):
    """
    INVOICE ENGINE MODULE: Sirf PDF core drawing logic handle karega.
    """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setTitle(f"Invoice_{client.id}")
    
    width, height = letter

    # 🖼️ Brand Logo Setup
    logo_path = os.path.join(settings.BASE_DIR, 'licensing', 'static', 'images', 'favicon.png')
    
    # ON ERROR HANDLING: Pehle check karenge ki file naye path par exist karti hai ya nahi
    if os.path.exists(logo_path):
        # drawImage(path, x, y, width, height, mask='auto')
        # PNG image perfectly load ho jayegi, .ico file yahan use nahi karni hai
        p.drawImage(logo_path, 40, height - 70, width=50, height=50, mask='auto')
        
        # Logo drawing match lines (Text positioning aligned)
        p.setFillColor(colors.HexColor("#1e293b"))
        p.setFont("Helvetica-Bold", 16)
        p.drawString(105, height - 45, "INVOICE")
        p.setFont("Helvetica-Bold", 11)
        p.setFillColor(colors.HexColor("#0f172a"))
        p.drawString(105, height - 60, "Web Automation With Excel VBA")
    else:
        # FALLBACK LOGIC: Agar kisi wajah se image delete ya missing ho, to bina crash kiye text chalega
        p.setFillColor(colors.HexColor("#094d25"))
        p.setFont("Helvetica-Bold", 18)
        p.drawString(40, height - 50, "INVOICE")
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(colors.HexColor("#094d25"))
        p.drawString(40, height - 70, "Web Automation With Excel VBA")
        
    # Company Details
    p.setFont("Helvetica", 9)
    p.setFillColor(colors.HexColor("#475569"))
    p.drawString(40, height - 90, "Dilip Delwash Utilities")
    p.drawString(40, height - 102, "Gurla Road Unhel, Unhel, 456221")
    p.drawString(40, height - 114, "Email: ddelwash8@gmail.com | Mob: +91 90397 79483")

    # Invoice Meta
    p.setFillColor(colors.HexColor("#0f172a"))
    p.setFont("Helvetica-Bold", 10)
    # nextText = datetime(client.date_time).year()
    # forWhy = ''.join(word[0] for word in client.for_whys.split()).upper()
    p.drawRightString(width - 40, height - 50, f"INVOICE NO: { client.for_whys}-{client.id if client.id else '6477'}")
    p.setFont("Helvetica", 10)
    p.drawRightString(width - 40, height - 65, f"Date: {datetime.now().strftime('%d-%m-%Y')}")

    p.setStrokeColor(colors.HexColor("#cbd5e1"))
    p.setLineWidth(1)
    p.line(40, height - 130, width - 40, height - 130)

    # Billing Section
    block_top = height - 155
    p.setFillColor(colors.HexColor("#094d25"))
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, block_top, "BILL TO")
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(40, block_top - 15, f"PACS/Bank: {client.pacs_name if client.pacs_name else '-'}")
    p.setFont("Helvetica", 9)
    p.drawString(40, block_top - 27, f"Branch: {client.brach if client.brach else '-'}")
    p.drawString(40, block_top - 39, f"Dist: {client.dist if client.dist else '-'}")
    p.drawString(40, block_top - 51, f"Mob: {client.mobile if client.mobile else '-'}")

    p.setFillColor(colors.HexColor("#094d25"))
    p.setFont("Helvetica-Bold", 10)
    p.drawString(320, block_top, "SHIP TO")
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(320, block_top - 15, f"PACS/Bank: {client.pacs_name if client.pacs_name else '-'}")
    p.setFont("Helvetica", 9)
    p.drawString(320, block_top - 27, f"Branch: {client.brach if client.brach else '-'}")
    p.drawString(320, block_top - 39, f"Dist: {client.dist if client.dist else '-'}")

    # Calculations
    total_paid = float(client.amount if client.amount else 0.0)
    try:
        if customAmount != '':
            total_paid = int(customAmount)
    except:
        customAmount = 0
    if total_paid > 0:
        subtotal = round(total_paid / 1.18, 2)
        tax_amount = round(total_paid - subtotal, 2)
    else:
        subtotal = 0.0
        tax_amount = 0.0

    # Grid Header
    table_top = height - 245
    p.setFillColor(colors.HexColor("#094d25"))
    p.rect(40, table_top - 20, width - 80, 20, stroke=0, fill=1)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(45, table_top - 14, "DESCRIPTION")
    p.drawCentredString(320, table_top - 14, "QTY")
    p.drawCentredString(380, table_top - 14, "UNIT")
    p.drawRightString(470, table_top - 14, "PRICE (Rs.)")
    p.drawRightString(width - 45, table_top - 14, "TOTAL (Rs.)")

    # Data Row
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 9)
    # f_year_str = client.f_year if client.f_year else "2024-2025"
    p.drawString(45, table_top - 40, f"{client.for_whys} {client.f_year} (Utility License)")
    p.drawCentredString(320, table_top - 40, "1")
    p.drawCentredString(380, table_top - 40, "Rs.")
    p.drawRightString(470, table_top - 40, f"{subtotal:,.2f}")
    p.drawRightString(width - 45, table_top - 40, f"{subtotal:,.2f}")

    p.setStrokeColor(colors.HexColor("#cbd5e1"))
    p.line(40, table_top - 55, width - 40, table_top - 55)

    # Tax Block Summary
    calc_top = table_top - 80
    right_align_label = width - 180
    right_align_val = width - 45
    
    p.setFont("Helvetica", 9)
    p.drawString(right_align_label, calc_top, "SUBTOTAL:")
    p.drawRightString(right_align_val, calc_top, f"Rs. {subtotal:,.2f}")
    # p.drawString(right_align_label, calc_top - 15, "DISCOUNT:")
    # p.drawRightString(right_align_val, calc_top - 15, "Rs. 0.00")
    p.drawString(right_align_label, calc_top - 30, "TAX RATE (GST):")
    p.drawRightString(right_align_val, calc_top - 30, "18.00%")
    p.drawString(right_align_label, calc_top - 45, "TOTAL TAX AMOUNT:")
    p.drawRightString(right_align_val, calc_top - 45, f"Rs. {tax_amount:,.2f}")

    p.setFillColor(colors.HexColor("#f1f5f9"))
    p.rect(right_align_label - 10, calc_top - 72, 150, 22, stroke=0, fill=1)
    p.setFillColor(colors.HexColor("#0f172a"))
    p.setFont("Helvetica-Bold", 10)
    p.drawString(right_align_label, calc_top - 64, "TOTAL PAID:")
    p.drawRightString(right_align_val, calc_top - 64, f"Rs. {total_paid:,.2f}")

    p.setStrokeColor(colors.HexColor("#e2e8f0"))
    p.line(40, 60, width - 40, 60)
    p.setFillColor(colors.gray)
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(40, 45, "* This is a computer-generated dynamic invoice based on centralized secure backend activation. No physical signature required.")
    p.drawRightString(width - 40, 45, "Page 1 of 1")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


# licensing/utils.py ke sabse niche ye naya function add karein

# licensing/utils.py ke andar ye dusra function add karein

def generate_erp_invoice_pdf(request, record):
    """
    NCL ERP INVOICE ENGINE: Copying the exact green branding layout (#094d25) 
    from userinfo but customized for tblPacsErp database models.
    """
    # ON ERROR HANDLING: Structural validation to ensure zero breakdown on runtime
    try:
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        p.setTitle(f"Invoice_ERP_{record.id}")
        
        width, height = letter

        # 🖼️ Brand Logo Setup (Same logic and folder path structure)
        logo_path = os.path.join(settings.BASE_DIR, 'licensing', 'static', 'images', 'favicon.png')
        
        if os.path.exists(logo_path):
            p.drawImage(logo_path, 40, height - 70, width=50, height=50, mask='auto')
            
            p.setFillColor(colors.HexColor("#1e293b"))
            p.setFont("Helvetica-Bold", 16)
            p.drawString(105, height - 45, "INVOICE (ERP MODULE)")
            p.setFont("Helvetica-Bold", 11)
            p.setFillColor(colors.HexColor("#0f172a"))
            p.drawString(105, height - 60, "Web Automation With Excel")
        else:
            p.setFillColor(colors.HexColor("#094d25"))
            p.setFont("Helvetica-Bold", 18)
            p.drawString(40, height - 50, "INVOICE (ERP MODULE)")
            p.setFont("Helvetica-Bold", 12)
            p.setFillColor(colors.HexColor("#094d25"))
            p.drawString(40, height - 70, "Web Automation With Excel")
            
        # Company Details (Same as your shared template)
        p.setFont("Helvetica", 9)
        p.setFillColor(colors.HexColor("#475569"))
        p.drawString(40, height - 90, "Dilip Delwash Utilities")
        p.drawString(40, height - 102, "Gurla Road Unhel, Unhel, 456221")
        p.drawString(40, height - 114, "Email: ddelwash8@gmail.com | Mob: +91 90397 79483")

        # Invoice Meta (Customized for ERP Tracking)
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica-Bold", 10)
        p.drawRightString(width - 40, height - 50, f"INVOICE NO: ERP-{record.id}")
        p.setFont("Helvetica", 10)
        p.drawRightString(width - 40, height - 65, f"Date: {datetime.now().strftime('%d-%m-%Y')}")

        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.setLineWidth(1)
        p.line(40, height - 130, width - 40, height - 130)

        # Billing Section (Aligned to the exact positions of your userinfo layout)
        block_top = height - 155
        p.setFillColor(colors.HexColor("#094d25"))
        p.setFont("Helvetica-Bold", 10)
        p.drawString(40, block_top, "BILL TO")
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(40, block_top - 15, f"PACS/Bank: {record.pacs_name if record.pacs_name else '-'}")
        p.setFont("Helvetica", 9)
        p.drawString(40, block_top - 27, f"Branch: {record.brach if record.brach else '-'}")
        p.drawString(40, block_top - 39, f"Dist / State: {record.dist if record.dist else '-'} / {record.state if record.state else '-'}")
        p.drawString(40, block_top - 51, f"Mob: {record.operator_mobile if record.operator_mobile else '-'}")

        p.setFillColor(colors.HexColor("#094d25"))
        p.setFont("Helvetica-Bold", 10)
        p.drawString(320, block_top, "SYSTEM ROUTE LINK")
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(320, block_top - 15, f"System ID: {record.system_id if record.system_id else '-'}")
        p.setFont("Helvetica", 9)
        
        # Safe Date Conversion fallback formatting
        expiry_str = record.expiry_date.strftime('%d-%m-%Y') if record.expiry_date else '-'
        p.drawString(320, block_top - 27, f"Expiry Date: {expiry_str}")
        
        # Log Remark limit length mapping
        remark_str = record.remark[:35] if record.remark else '-'
        p.drawString(320, block_top - 39, f"Remark Log: {remark_str}")

        # Calculations (Backwards GST Breakdown Engine)
        total_paid = float(record.amount if record.amount else 0.0)
        custom_amount = request.GET.get('customAmount', '').strip()
        if custom_amount:
            try:
                total_paid = float(custom_amount)
            except (TypeError, ValueError):
                pass
        if total_paid > 0:
            subtotal = round(total_paid / 1.18, 2)
            tax_amount = round(total_paid - subtotal, 2)
        else:
            subtotal = 0.0
            tax_amount = 0.0

        # Grid Header (Green Theme Match #094d25)
        table_top = height - 245
        p.setFillColor(colors.HexColor("#094d25"))
        p.rect(40, table_top - 20, width - 80, 20, stroke=0, fill=1)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(45, table_top - 14, "DESCRIPTION")
        p.drawCentredString(320, table_top - 14, "QTY")
        p.drawCentredString(380, table_top - 14, "UNIT")
        p.drawRightString(470, table_top - 14, "PRICE (Rs.)")
        p.drawRightString(width - 45, table_top - 14, "TOTAL (Rs.)")

        # Data Row (NCL Module Dynamic Layout String)
        p.setFillColor(colors.black)
        p.setFont("Helvetica", 9)
        p.drawString(45, table_top - 40, f"PacsErp System Module License (ID: {record.erp_id if record.erp_id else '-'})")
        p.drawCentredString(320, table_top - 40, "1")
        p.drawCentredString(380, table_top - 40, "Rs.")
        p.drawRightString(470, table_top - 40, f"{subtotal:,.2f}")
        p.drawRightString(width - 45, table_top - 40, f"{subtotal:,.2f}")

        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.line(40, table_top - 55, width - 40, table_top - 55)

        # Tax Block Summary Panel
        calc_top = table_top - 80
        right_align_label = width - 180
        right_align_val = width - 45
        
        p.setFont("Helvetica", 9)
        p.drawString(right_align_label, calc_top, "SUBTOTAL:")
        p.drawRightString(right_align_val, calc_top, f"Rs. {subtotal:,.2f}")
        p.drawString(right_align_label, calc_top - 30, "TAX RATE (GST):")
        p.drawRightString(right_align_val, calc_top - 30, "18.00%")
        p.drawString(right_align_label, calc_top - 45, "TOTAL TAX AMOUNT:")
        p.drawRightString(right_align_val, calc_top - 45, f"Rs. {tax_amount:,.2f}")

        # Total Paid Bottom Highlight Grid Box
        p.setFillColor(colors.HexColor("#f1f5f9"))
        p.rect(right_align_label - 10, calc_top - 72, 150, 22, stroke=0, fill=1)
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica-Bold", 10)
        p.drawString(right_align_label, calc_top - 64, "TOTAL PAID:")
        p.drawRightString(right_align_val, calc_top - 64, f"Rs. {total_paid:,.2f}")

        # Standard Footer Layer
        p.setStrokeColor(colors.HexColor("#e2e8f0"))
        p.line(40, 60, width - 40, 60)
        p.setFillColor(colors.gray)
        p.setFont("Helvetica-Oblique", 8)
        p.drawString(40, 45, "* This is a computer-generated dynamic invoice based on centralized secure backend activation. No physical signature required.")
        p.drawRightString(width - 40, 45, "Page 1 of 1")

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        # Fallback thread routing safety catch
        raise Exception(f"ERP PDF Generation internal failure: {str(e)}")