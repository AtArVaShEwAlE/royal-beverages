"""
Email Utility Functions for Royal Beverages
Handles sending order status notifications with invoice attachments
"""
from flask import current_app, render_template_string
from flask_mail import Mail, Message
from io import BytesIO
from datetime import datetime
import os

# Initialize Flask-Mail (will be configured in app.py)
mail = Mail()

def generate_invoice_pdf(order_data, items):
    """
    Generate PDF invoice for an order
    Returns BytesIO object containing the PDF
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Company Header
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    elements.append(Paragraph("ROYAL BEVERAGES", company_style))
    elements.append(Paragraph("Tea Premix, Coffee Premix & Lemon Tea Supplier", styles['Normal']))
    elements.append(Paragraph("New Sangavi, Pune, Maharashtra", styles['Normal']))
    elements.append(Paragraph("GST: 27CUZPS1971H1ZP | Contact: 8888643340", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Invoice Title
    invoice_style = ParagraphStyle('InvoiceTitle', parent=styles['Heading2'], alignment=TA_CENTER)
    elements.append(Paragraph(f"INVOICE #{order_data['order_id']}", invoice_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Order Details
    details_data = [
        ['Order Date:', order_data['order_date']],
        ['Client:', order_data['client_name']],
        ['Status:', order_data['status']],
        ['Payment:', order_data['payment_status']]
    ]
    
    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2c3e50')),
    ]))
    
    elements.append(details_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Items Table
    items_data = [['#', 'Product', 'Quantity', 'Unit Price', 'GST%', 'Total']]
    
    for idx, item in enumerate(items, 1):
        items_data.append([
            str(idx),
            item['product_name'],
            str(item['quantity']),
            f"₹{item['unit_price']:.2f}",
            f"{item['gst_rate']}%",
            f"₹{item['total_amount']:.2f}"
        ])
    
    # Add totals
    items_data.append(['', '', '', '', 'Subtotal:', f"₹{order_data['subtotal']:.2f}"])
    items_data.append(['', '', '', '', 'GST:', f"₹{order_data['gst_amount']:.2f}"])
    items_data.append(['', '', '', '', 'Grand Total:', f"₹{order_data['grand_total']:.2f}"])
    
    items_table = Table(items_data, colWidths=[0.5*inch, 2.5*inch, 1*inch, 1.2*inch, 1*inch, 1.3*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -4), 1, colors.grey),
        ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Footer
    elements.append(Paragraph("Thank you for your business!", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def send_order_status_email(order_id, new_status, client_email, client_name):
    """
    Send email notification when order status changes
    
    Args:
        order_id: Order ID
        new_status: New status (approved, dispatched, delivered)
        client_email: Client's email address
        client_name: Client's name
    """
    try:
        # Email subject based on status
        subject_map = {
            'approved': f'Order #{order_id} - Approved ✓',
            'dispatched': f'Order #{order_id} - Dispatched 🚚',
            'delivered': f'Order #{order_id} - Delivered ✓',
            'cancelled': f'Order #{order_id} - Cancelled ✗'
        }
        
        subject = subject_map.get(new_status.lower(), f'Order #{order_id} - Status Update')
        
        # Create email message
        msg = Message(
            subject=subject,
            recipients=[client_email],
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Email body based on status
        if new_status.lower() == 'approved':
            msg.html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                    <h2 style="color: #27ae60; border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                        Order Approved ✓
                    </h2>
                    
                    <p>Dear {client_name},</p>
                    
                    <p>Great news! Your order <strong>#{order_id}</strong> has been <strong>approved</strong> and is being processed.</p>
                    
                    <div style="background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #2c3e50;">Order Details:</h3>
                        <p style="margin: 5px 0;"><strong>Order ID:</strong> #{order_id}</p>
                        <p style="margin: 5px 0;"><strong>Status:</strong> Approved</p>
                        <p style="margin: 5px 0;"><strong>Date:</strong> {datetime.now().strftime('%d %B %Y, %I:%M %p')}</p>
                    </div>
                    
                    <p>Your invoice is attached to this email for your reference.</p>
                    
                    <p>We will notify you once your order is dispatched.</p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        <strong>Royal Beverages</strong><br>
                        New Sangavi, Pune, Maharashtra<br>
                        Contact: 8888643340 | Email: royal.beveragesordersgmail.com<br>
                        GST: 27CUZPS1971H1ZP
                    </p>
                </div>
            </body>
            </html>
            """
            
        elif new_status.lower() == 'dispatched':
            msg.html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                    <h2 style="color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                        Order Dispatched 🚚
                    </h2>
                    
                    <p>Dear {client_name},</p>
                    
                    <p>Your order <strong>#{order_id}</strong> has been <strong>dispatched</strong> and is on its way!</p>
                    
                    <div style="background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #2c3e50;">Delivery Information:</h3>
                        <p style="margin: 5px 0;"><strong>Order ID:</strong> #{order_id}</p>
                        <p style="margin: 5px 0;"><strong>Status:</strong> Dispatched</p>
                        <p style="margin: 5px 0;"><strong>Dispatched On:</strong> {datetime.now().strftime('%d %B %Y, %I:%M %p')}</p>
                    </div>
                    
                    <p>Your order will be delivered soon. We will notify you once it's delivered.</p>
                    
                    <p>Thank you for choosing Royal Beverages!</p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        <strong>Royal Beverages</strong><br>
                        New Sangavi, Pune, Maharashtra<br>
                        Contact: 8888643340 | Email: royal.beverages82@gmail.com
                    </p>
                </div>
            </body>
            </html>
            """
            
        elif new_status.lower() == 'delivered':
            msg.html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                    <h2 style="color: #27ae60; border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                        Order Delivered ✓
                    </h2>
                    
                    <p>Dear {client_name},</p>
                    
                    <p>Your order <strong>#{order_id}</strong> has been successfully <strong>delivered</strong>!</p>
                    
                    <div style="background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #2c3e50;">Delivery Confirmation:</h3>
                        <p style="margin: 5px 0;"><strong>Order ID:</strong> #{order_id}</p>
                        <p style="margin: 5px 0;"><strong>Status:</strong> Delivered</p>
                        <p style="margin: 5px 0;"><strong>Delivered On:</strong> {datetime.now().strftime('%d %B %Y, %I:%M %p')}</p>
                    </div>
                    
                    <p>We hope you're satisfied with your order!</p>
                    
                    <p>If you have any questions or concerns, please don't hesitate to contact us.</p>
                    
                    <p style="font-style: italic; color: #7f8c8d;">Thank you for your business. We look forward to serving you again!</p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        <strong>Royal Beverages</strong><br>
                        New Sangavi, Pune, Maharashtra<br>
                        Contact: 8888643340 | Email: royal.beverages82@gmail.com
                    </p>
                </div>
            </body>
            </html>
            """
        
        # If status is 'approved', attach invoice
        if new_status.lower() == 'approved':
            # Fetch order details from database
            
            if current_app.config.get('USE_POSTGRES', False):
                # PostgreSQL query
                db = current_app.extensions.get('sqlalchemy')
                query = f"""
                    SELECT o.*, c.company_name, c.address, c.contact_person
                    FROM orders o
                    JOIN clients c ON o.client_id = c.client_id
                    WHERE o.order_id = {order_id}
                """
                result = db.session.execute(db.text(query))
                order = dict(result.fetchone()._mapping) if result else None
            else:
                # MySQL query
                mysql = current_app.extensions.get('mysql')
                cursor = mysql.connection.cursor()
                cursor.execute("""
                    SELECT o.*, c.company_name, c.address, c.contact_person
                    FROM orders o
                    JOIN clients c ON o.client_id = c.client_id
                    WHERE o.order_id = %s
                """, (order_id,))
                order = cursor.fetchone()
                cursor.close()
            
            if order:
                # Fetch order items
                if current_app.config.get('USE_POSTGRES', False):
                    query = f"""
                        SELECT oi.*, p.name as product_name
                        FROM order_items oi
                        JOIN products p ON oi.product_id = p.product_id
                        WHERE oi.order_id = {order_id}
                    """
                    result = db.session.execute(db.text(query))
                    items = [dict(row._mapping) for row in result]
                else:
                    cursor = mysql.connection.cursor()
                    cursor.execute("""
                        SELECT oi.*, p.name as product_name
                        FROM order_items oi
                        JOIN products p ON oi.product_id = p.product_id
                        WHERE oi.order_id = %s
                    """, (order_id,))
                    items = cursor.fetchall()
                    cursor.close()
                
                # Prepare order data
                order_data = {
                    'order_id': order['order_id'],
                    'order_date': order['order_date'].strftime('%d %B %Y') if hasattr(order['order_date'], 'strftime') else str(order['order_date']),
                    'client_name': order['company_name'],
                    'status': order['status'],
                    'payment_status': order['payment_status'],
                    'subtotal': float(order['subtotal']),
                    'gst_amount': float(order['gst_amount']),
                    'grand_total': float(order['grand_total'])
                }
                
                # Generate PDF
                pdf_buffer = generate_invoice_pdf(order_data, items)
                
                # Attach PDF
                msg.attach(
                    f"Invoice_{order_id}.pdf",
                    "application/pdf",
                    pdf_buffer.read()
                )
        
        # Send email
        mail.send(msg)
        return True, "Email sent successfully"
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False, str(e)