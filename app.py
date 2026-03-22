from flask import Flask, render_template, redirect, url_for, session, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
try:
    from flask_mysqldb import MySQL
except ImportError:
    MySQL = None 
from werkzeug.security import check_password_hash, generate_password_hash
from config import config
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
from flask import send_file
from datetime import datetime, timedelta
import calendar
import hashlib
import re
import os

# Initialize Flask app
app = Flask(__name__)

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30 days
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config.from_object(config['development'])

if app.config.get('USE_POSTGRES', False):
    # PostgreSQL via SQLAlchemy
    db = SQLAlchemy(app)
    mysql = None
else:
    # MySQL
    mysql = MySQL(app)
    db = None


@app.context_processor
def inject_outstanding_count():
    """Inject outstanding payment count into all templates"""
    outstanding_count = 0
    
    # Only calculate for logged-in admin/staff users
    if 'user_id' in session and session.get('role') in ['admin', 'staff']:
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM orders 
                WHERE payment_status IN ('pending', 'partial')
            """)
            result = cursor.fetchone()
            outstanding_count = result['count'] if result else 0
            cursor.close()
        except Exception as e:
            print(f"Error getting outstanding count: {str(e)}")
            outstanding_count = 0
    
    return dict(outstanding_count=outstanding_count)

@app.route('/')
def index():
    """Home page - redirects to login or dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login - WITH REMEMBER ME"""
    # If already logged in, redirect
    if 'user_id' in session:
        if session.get('role') in ['admin', 'staff']:
            return redirect(url_for('dashboard'))
        return redirect(url_for('client_dashboard'))
    
    # Handle POST (login attempt)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')  # Get remember me checkbox
        
        try:
            cursor = mysql.connection.cursor()
            
            # Get user by username
            cursor.execute("""
                SELECT user_id, username, password_hash, email, role, 
                       is_active, first_name, last_name
                FROM users 
                WHERE username = %s
            """, (username,))
            
            user = cursor.fetchone()
            cursor.close()
            
            # Check if user exists and is active
            if not user:
                flash('Invalid username or password', 'danger')
                return render_template('login.html')
            
            if not user['is_active']:
                flash('Account is inactive', 'danger')
                return render_template('login.html')
            
            # Verify password
            from werkzeug.security import check_password_hash
            
            if check_password_hash(user['password_hash'], password):
                # Password correct - create session
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['first_name'] = user['first_name']
                session['last_name'] = user['last_name']
                
                # NEW: Make session permanent if Remember Me checked
                if remember:
                    session.permanent = True  # Lasts 30 days
                else:
                    session.permanent = False  # Expires when browser closes
                
                # Redirect based on role
                if user['role'] in ['admin', 'staff']:
                    return redirect(url_for('dashboard'))
                else:
                    return redirect(url_for('client_dashboard'))
            else:
                # Password incorrect
                flash('Invalid username or password', 'danger')
                return render_template('login.html')
        
        except Exception as e:
            print(f"Login error: {str(e)}")
            import traceback
            traceback.print_exc()
            flash('An error occurred. Please try again.', 'danger')
            return render_template('login.html')
    
    # GET request - show login form
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup page with password validation and MANDATORY GST"""
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        username = request.form.get('username')
        phone = request.form.get('phone')
        organization = request.form.get('organization')
        gst_number = request.form.get('gst_number', '').strip().upper()  # MANDATORY
        role = request.form.get('role', 'client')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # GST validation - MANDATORY
        if not gst_number:
            return render_template('signup.html', error='GST Number is required')
        
        # Validate GST format
        gst_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        if not re.match(gst_pattern, gst_number):
            return render_template('signup.html', error='Invalid GST number format. Example: 27CUZPS1971H1ZP')
        
        # Password validation
        if password != confirm_password:
            return render_template('signup.html', error='Passwords do not match')
        
        # Check password requirements
        if len(password) < 8:
            return render_template('signup.html', error='Password must be at least 8 characters')
        
        if not re.search(r'[A-Z]', password):
            return render_template('signup.html', error='Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', password):
            return render_template('signup.html', error='Password must contain at least one lowercase letter')
        
        if not re.search(r'[0-9]', password):
            return render_template('signup.html', error='Password must contain at least one number')
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
            return render_template('signup.html', error='Password must contain at least one special character')
        
        try:
            cursor = mysql.connection.cursor()
            
            # Check username exists
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                cursor.close()
                return render_template('signup.html', error='Username already exists')
            
            # Check email exists
            cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                cursor.close()
                return render_template('signup.html', error='Email already exists')
            
            # Check if GST number already exists
            cursor.execute("SELECT client_id FROM clients WHERE gst_number = %s", (gst_number,))
            if cursor.fetchone():
                cursor.close()
                return render_template('signup.html', error='GST Number already registered')
            
            # Hash password using werkzeug (portable across all environments)
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash(password)
            
            # Insert user
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, first_name, last_name, phone, role, is_active) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (username, email, password_hash, first_name, last_name, phone, role))
            
            user_id = cursor.lastrowid
            
            # If client, create client profile with GST
            if role == 'client' and organization:
                cursor.execute("""
                    INSERT INTO clients (
                        user_id, organization_name, organization_type, 
                        address, city, state, pincode, 
                        contact_person, contact_email, contact_phone, gst_number
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id, organization, 'other', 'N/A', 'N/A', 'N/A', '000000', 
                      f"{first_name} {last_name}", email, phone, gst_number))
            
            mysql.connection.commit()
            cursor.close()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            mysql.connection.rollback()
            print(f"Signup error: {str(e)}")
            import traceback
            traceback.print_exc()
            return render_template('signup.html', error='An error occurred. Please try again.')
    
    return render_template('signup.html')


@app.route('/dashboard')
def dashboard():
    """Admin dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Total orders
        cursor.execute("SELECT COUNT(*) as count FROM orders")
        total_orders = cursor.fetchone()['count']
        
        # Pending orders
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()['count']
        
        # Total revenue
        cursor.execute("SELECT COALESCE(SUM(grand_total), 0) as total FROM orders WHERE status != 'cancelled'")
        total_revenue = float(cursor.fetchone()['total'])
        
        # Total clients
        cursor.execute("SELECT COUNT(*) as count FROM clients")
        total_clients = cursor.fetchone()['count']
        
        # NEW: Outstanding payments count
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM orders 
            WHERE payment_status IN ('pending', 'partial')
        """)
        outstanding_count = cursor.fetchone()['count']
        
        # Recent orders (last 5)
        cursor.execute("""
            SELECT o.order_id, o.order_number, o.order_date, o.grand_total, o.status,
                   c.organization_name
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            ORDER BY o.order_date DESC
            LIMIT 5
        """)
        recent_orders = cursor.fetchall()
        
        # Recent activity
        recent_activity = []
        
        # Latest order
        cursor.execute("""
            SELECT o.order_number, o.created_at, c.organization_name
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            ORDER BY o.created_at DESC
            LIMIT 1
        """)
        latest_order = cursor.fetchone()
        if latest_order:
            recent_activity.append({
                'activity_type': 'order',
                'description': f"New order {latest_order['order_number']} from {latest_order['organization_name']}",
                'time': latest_order['created_at'].strftime('%d %b %Y, %I:%M %p')
            })
        
        # Latest stock change
        cursor.execute("""
            SELECT sl.quantity_changed, sl.created_at, p.product_name, sl.log_type
            FROM stock_logs sl
            JOIN products p ON sl.product_id = p.product_id
            ORDER BY sl.created_at DESC
            LIMIT 1
        """)
        latest_stock = cursor.fetchone()
        if latest_stock:
            action = 'added' if latest_stock['quantity_changed'] > 0 else 'removed'
            recent_activity.append({
                'activity_type': 'stock',
                'description': f"Stock {action}: {abs(latest_stock['quantity_changed'])} units of {latest_stock['product_name']}",
                'time': latest_stock['created_at'].strftime('%d %b %Y, %I:%M %p')
            })
        
        # Latest client
        cursor.execute("""
            SELECT c.organization_name, u.created_at
            FROM clients c
            JOIN users u ON c.user_id = u.user_id
            ORDER BY u.created_at DESC
            LIMIT 1
        """)
        latest_client = cursor.fetchone()
        if latest_client:
            recent_activity.append({
                'activity_type': 'client',
                'description': f"New client registered: {latest_client['organization_name']}",
                'time': latest_client['created_at'].strftime('%d %b %Y, %I:%M %p')
            })
        
        cursor.close()
        
        return render_template('dashboard.html',
                             total_orders=total_orders,
                             pending_orders=pending_orders,
                             total_revenue=total_revenue,
                             total_clients=total_clients,
                             recent_orders=recent_orders,
                             recent_activity=recent_activity,
                             outstanding_count=outstanding_count)  # NEW
    
    except Exception as e:
        import traceback
        print(f"Dashboard error: {str(e)}")
        traceback.print_exc()
        return render_template('dashboard.html',
                             total_orders=0,
                             pending_orders=0,
                             total_revenue=0,
                             total_clients=0,
                             recent_orders=[],
                             recent_activity=[],
                             outstanding_count=0)  # NEW
 
 
@app.route('/client/dashboard')
def client_dashboard():
    """Client dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'client':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get client_id
        cursor.execute("SELECT client_id FROM clients WHERE user_id = %s", (session['user_id'],))
        client = cursor.fetchone()
        
        if not client:
            flash('Client profile not found', 'danger')
            return redirect(url_for('login'))
        
        client_id = client['client_id']
        
        # Total orders
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE client_id = %s", (client_id,))
        total_orders = cursor.fetchone()['count']
        
        # Pending orders
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE client_id = %s AND status = 'pending'", (client_id,))
        pending_orders = cursor.fetchone()['count']
        
        # Delivered orders
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE client_id = %s AND status = 'delivered'", (client_id,))
        delivered_orders = cursor.fetchone()['count']
        
        # Total spent
        cursor.execute("""
            SELECT COALESCE(SUM(grand_total), 0) as total 
            FROM orders 
            WHERE client_id = %s AND status != 'cancelled'
        """, (client_id,))
        total_spent = float(cursor.fetchone()['total'])
        
        # Recent orders with item count
        cursor.execute("""
            SELECT o.order_id, o.order_number, o.order_date, o.grand_total, o.status,
                   COUNT(oi.order_item_id) as item_count
            FROM orders o
            LEFT JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.client_id = %s
            GROUP BY o.order_id
            ORDER BY o.order_date DESC
            LIMIT 5
        """, (client_id,))
        recent_orders = cursor.fetchall()
        
        cursor.close()
        
        return render_template('client_dashboard.html',
                             total_orders=total_orders,
                             pending_orders=pending_orders,
                             delivered_orders=delivered_orders,
                             total_spent=total_spent,
                             recent_orders=recent_orders,
                             outstanding_count=0)  # NEW - clients don't need this but base.html checks for it
    
    except Exception as e:
        import traceback
        print(f"Client dashboard error: {str(e)}")
        traceback.print_exc()
        return render_template('client_dashboard.html',
                             total_orders=0,
                             pending_orders=0,
                             delivered_orders=0,
                             total_spent=0,
                             recent_orders=[],
                             outstanding_count=0)  # NEW
# ================================================
# PRODUCT MANAGEMENT ROUTES
# ================================================

@app.route('/products')
def products():
    """View all products - ADMIN/STAFF ONLY"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Block clients from accessing products management page
    if session.get('role') == 'client':
        flash('Access denied. Please use "Place Order" to view products.', 'warning')
        return redirect(url_for('place_order'))
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            SELECT p.*, c.category_name 
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            ORDER BY p.product_id DESC
        """)
        products = cursor.fetchall()
        
        # DEBUG: Print what we got
        print(f"=== DEBUG PRODUCTS ===")
        print(f"Type: {type(products)}")
        print(f"Length: {len(products) if products else 'None'}")
        print(f"Products: {products}")
        print(f"======================")
        
        cursor.execute("SELECT * FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        
        active_count = sum(1 for p in products if p['is_active'])
        
        cursor.close()
        
        return render_template('products.html', 
                             products=products,
                             categories=categories,
                             active_count=active_count)
        
    except Exception as e:
        print(f"Products error: {str(e)}")
        import traceback
        traceback.print_exc()  # Print full error
        flash('Error loading products', 'danger')
        return render_template('products.html', 
                             products=[],
                             categories=[],
                             active_count=0)
    
@app.route('/products/add', methods=['GET'])
def add_product():
    """Add new product page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        flash('Access denied. Only admin can add products.', 'danger')
        return redirect(url_for('products'))
    
    return render_template('add_product.html')


@app.route('/products/add/submit', methods=['POST'])
def add_product_submit():
    """Handle add product form submission"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        flash('Access denied. Only admin can add products.', 'danger')
        return redirect(url_for('products'))
    
    try:
        product_name = request.form.get('product_name')
        category_id = request.form.get('category_id')
        packaging_size = request.form.get('packaging_size')
        unit_price = request.form.get('unit_price')
        gst_percentage = request.form.get('gst_percentage')
        description = request.form.get('description', '')
        initial_stock = request.form.get('initial_stock', 0)
        minimum_stock = request.form.get('minimum_stock', 10)
        is_active = 1 if request.form.get('is_active') else 0
        
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            INSERT INTO products (category_id, product_name, description, packaging_size, 
                                unit_price, gst_percentage, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (category_id, product_name, description, packaging_size, 
              unit_price, gst_percentage, is_active))
        
        product_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO inventory (product_id, quantity_in_stock, minimum_stock_level)
            VALUES (%s, %s, %s)
        """, (product_id, initial_stock, minimum_stock))
        
        if int(initial_stock) > 0:
            cursor.execute("""
                INSERT INTO stock_logs (product_id, quantity_changed, log_type, reason, logged_by)
                VALUES (%s, %s, 'addition', 'Initial stock', %s)
            """, (product_id, initial_stock, session['user_id']))
        
        mysql.connection.commit()
        cursor.close()
        
        flash(f'Product "{product_name}" added successfully!', 'success')
        return redirect(url_for('products'))
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Add product error: {str(e)}")
        flash('Error adding product. Please try again.', 'danger')
        return redirect(url_for('add_product'))


@app.route('/products/edit/<int:product_id>', methods=['GET'])
def edit_product(product_id):
    """Edit product page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        flash('Access denied. Only admin can edit products.', 'danger')
        return redirect(url_for('products'))
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            SELECT p.*, c.category_name 
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.product_id = %s
        """, (product_id,))
        product = cursor.fetchone()
        
        if not product:
            flash('Product not found', 'danger')
            return redirect(url_for('products'))
        
        cursor.execute("""
            SELECT * FROM inventory WHERE product_id = %s
        """, (product_id,))
        inventory = cursor.fetchone()
        
        cursor.close()
        
        return render_template('edit_product.html', 
                             product=product,
                             inventory=inventory)
        
    except Exception as e:
        print(f"Edit product error: {str(e)}")
        flash('Error loading product', 'danger')
        return redirect(url_for('products'))


@app.route('/products/edit/<int:product_id>/submit', methods=['POST'])
def edit_product_submit(product_id):
    """Handle edit product form submission"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        flash('Access denied. Only admin can edit products.', 'danger')
        return redirect(url_for('products'))
    
    try:
        product_name = request.form.get('product_name')
        category_id = request.form.get('category_id')
        packaging_size = request.form.get('packaging_size')
        unit_price = request.form.get('unit_price')
        gst_percentage = request.form.get('gst_percentage')
        description = request.form.get('description', '')
        minimum_stock = request.form.get('minimum_stock', 10)
        is_active = 1 if request.form.get('is_active') else 0
        
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            UPDATE products 
            SET product_name = %s, 
                category_id = %s, 
                packaging_size = %s,
                unit_price = %s,
                gst_percentage = %s,
                description = %s,
                is_active = %s
            WHERE product_id = %s
        """, (product_name, category_id, packaging_size, unit_price, 
              gst_percentage, description, is_active, product_id))
        
        cursor.execute("""
            UPDATE inventory 
            SET minimum_stock_level = %s
            WHERE product_id = %s
        """, (minimum_stock, product_id))
        
        mysql.connection.commit()
        cursor.close()
        
        flash(f'Product "{product_name}" updated successfully!', 'success')
        return redirect(url_for('products'))
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Update product error: {str(e)}")
        flash('Error updating product. Please try again.', 'danger')
        return redirect(url_for('edit_product', product_id=product_id))


@app.route('/products/toggle/<int:product_id>')
def toggle_product_status(product_id):
    """Toggle product active/inactive status"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        flash('Access denied. Only admin can modify products.', 'danger')
        return redirect(url_for('products'))
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("SELECT is_active, product_name FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()
        
        if product:
            new_status = not product['is_active']
            cursor.execute("UPDATE products SET is_active = %s WHERE product_id = %s", 
                         (new_status, product_id))
            mysql.connection.commit()
            
            status_text = "activated" if new_status else "deactivated"
            flash(f'Product "{product["product_name"]}" {status_text} successfully!', 'success')
        else:
            flash('Product not found', 'danger')
        
        cursor.close()
        
    except Exception as e:
        print(f"Toggle product error: {str(e)}")
        flash('Error updating product status', 'danger')
    
    return redirect(url_for('products'))


# ================================================
# ORDER MANAGEMENT ROUTES
# ================================================

@app.route('/orders/place', methods=['GET'])
def place_order():
    """Place new order page - for clients"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'client':
        flash('Only clients can place orders', 'danger')
        return redirect(url_for('dashboard'))
    
    # NEW: Check for repeat order items
    repeat_items = session.pop('repeat_order_items', None)
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            SELECT p.*, c.category_name 
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.is_active = TRUE
            ORDER BY c.category_name, p.product_name
        """)
        products = cursor.fetchall()
        
        cursor.close()
        
        # NEW: Pass repeat_items to template
        return render_template('place_order.html', 
                             products=products,
                             repeat_items=repeat_items)
        
    except Exception as e:
        print(f"Place order error: {str(e)}")
        flash('Error loading products', 'danger')
        return redirect(url_for('client_dashboard'))

@app.route('/orders/place/submit', methods=['POST'])
def place_order_submit():
    """Handle place order form submission"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'client':
        flash('Only clients can place orders', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        total_amount = float(request.form.get('total_amount', 0))
        gst_amount = float(request.form.get('gst_amount', 0))
        grand_total = float(request.form.get('grand_total', 0))
        notes = request.form.get('notes', '')
        
        if grand_total <= 0:
            flash('Please select at least one product', 'danger')
            return redirect(url_for('place_order'))
        
        cursor = mysql.connection.cursor()
        
        cursor.execute("SELECT client_id FROM clients WHERE user_id = %s", (session['user_id'],))
        client = cursor.fetchone()
        
        if not client:
            flash('Client profile not found', 'danger')
            return redirect(url_for('client_dashboard'))
        
        client_id = client['client_id']
        
        order_number = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        cursor.execute("""
            INSERT INTO orders (client_id, order_number, total_amount, gst_amount, grand_total, status, notes)
            VALUES (%s, %s, %s, %s, %s, 'pending', %s)
        """, (client_id, order_number, total_amount, gst_amount, grand_total, notes))
        
        order_id = cursor.lastrowid
        
        for key in request.form:
            if key.startswith('quantity_'):
                product_id = int(key.split('_')[1])
                quantity = int(request.form.get(key, 0))
                
                if quantity > 0:
                    cursor.execute("SELECT unit_price, gst_percentage FROM products WHERE product_id = %s", (product_id,))
                    product = cursor.fetchone()
                    
                    if product:
                        unit_price = float(product['unit_price'])
                        gst_percentage = float(product['gst_percentage'])
                        total_price = quantity * unit_price
                        
                        cursor.execute("""
                            INSERT INTO order_items (order_id, product_id, quantity, unit_price, gst_percentage, total_price)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (order_id, product_id, quantity, unit_price, gst_percentage, total_price))
        
        mysql.connection.commit()
        cursor.close()
        
        flash(f'Order {order_number} placed successfully! Awaiting admin approval.', 'success')
        return redirect(url_for('client_dashboard'))
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Place order submit error: {str(e)}")
        flash('Error placing order. Please try again.', 'danger')
        return redirect(url_for('place_order'))

@app.route('/orders/my-orders')
def my_orders():
    """View client's own orders"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'client':
        flash('Access denied. This page is for clients only.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get client_id from user_id
        cursor.execute("SELECT client_id FROM clients WHERE user_id = %s", (session['user_id'],))
        client = cursor.fetchone()
        
        if not client:
            flash('Client profile not found', 'danger')
            return redirect(url_for('client_dashboard'))
        
        client_id = client['client_id']
        
        # Get all orders for this client
        cursor.execute("""
            SELECT o.*
            FROM orders o
            WHERE o.client_id = %s
            ORDER BY o.order_date DESC
        """, (client_id,))
        orders = cursor.fetchall()
        
        # Get order items for each order
        for order in orders:
            cursor.execute("""
                SELECT oi.*, p.product_name
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                WHERE oi.order_id = %s
            """, (order['order_id'],))
            order['order_items'] = cursor.fetchall()
        
        # Calculate statistics
        pending_count = 0
        delivered_count = 0
        total_spent = 0.0
        
        for o in orders:
            if o['status'] == 'pending':
                pending_count += 1
            if o['status'] == 'delivered':
                delivered_count += 1
            if o['status'] != 'cancelled':
                total_spent += float(o['grand_total'])
        
        cursor.close()
        
        return render_template('my_orders.html',
                             orders=orders,
                             pending_count=pending_count,
                             delivered_count=delivered_count,
                             total_spent=total_spent)
        
    except Exception as e:
        import traceback
        print(f"My orders error: {str(e)}")
        traceback.print_exc()
        
        flash('Error loading orders', 'danger')
        return render_template('my_orders.html',
                             orders=[],
                             pending_count=0,
                             delivered_count=0,
                             total_spent=0)

@app.route('/orders/manage')
def manage_orders():
    """Manage all orders - for admin"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get all orders with client details
        cursor.execute("""
            SELECT o.*, 
                   c.organization_name, c.contact_person, c.contact_email, c.contact_phone
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            ORDER BY o.order_date DESC
        """)
        orders = cursor.fetchall()
        
        # Get order items for each order - USE 'order_items' instead of 'items'
        for order in orders:
            cursor.execute("""
                SELECT oi.*, p.product_name
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                WHERE oi.order_id = %s
            """, (order['order_id'],))
            order['order_items'] = cursor.fetchall()  # CHANGED FROM 'items' to 'order_items'
        
        # Calculate statistics
        pending_count = 0
        delivered_count = 0
        total_revenue = 0.0
        
        for o in orders:
            if o['status'] == 'pending':
                pending_count += 1
            if o['status'] == 'delivered':
                delivered_count += 1
            if o['status'] != 'cancelled':
                total_revenue += float(o['grand_total'])
        
        cursor.close()
        
        return render_template('manage_orders.html',
                             orders=orders,
                             pending_count=pending_count,
                             delivered_count=delivered_count,
                             total_revenue=total_revenue)
        
    except Exception as e:
        import traceback
        print(f"Manage orders error: {str(e)}")
        traceback.print_exc()
        
        flash('Error loading orders', 'danger')
        return render_template('manage_orders.html',
                             orders=[],
                             pending_count=0,
                             delivered_count=0,
                             total_revenue=0)

@app.route('/orders/approve/<int:order_id>')
def approve_order(order_id):
    """Approve a pending order and deduct stock automatically"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get order details
        cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        
        if not order:
            flash('Order not found', 'danger')
            return redirect(url_for('manage_orders'))
        
        if order['status'] != 'pending':
            flash('Only pending orders can be approved', 'warning')
            return redirect(url_for('manage_orders'))
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, p.product_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        order_items = cursor.fetchall()
        
        # Check stock availability for all items
        insufficient_stock = []
        for item in order_items:
            cursor.execute("""
                SELECT quantity_in_stock 
                FROM inventory 
                WHERE product_id = %s
            """, (item['product_id'],))
            
            inventory = cursor.fetchone()
            
            if not inventory or inventory['quantity_in_stock'] < item['quantity']:
                insufficient_stock.append({
                    'product': item['product_name'],
                    'required': item['quantity'],
                    'available': inventory['quantity_in_stock'] if inventory else 0
                })
        
        # If any item has insufficient stock, don't approve
        if insufficient_stock:
            error_msg = 'Cannot approve order - Insufficient stock: '
            for item in insufficient_stock:
                error_msg += f"{item['product']} (need {item['required']}, have {item['available']}); "
            flash(error_msg, 'danger')
            cursor.close()
            return redirect(url_for('manage_orders'))
        
        # All stock is available - proceed with approval
        # Deduct stock for each item
        for item in order_items:
            # Update inventory
            cursor.execute("""
                UPDATE inventory 
                SET quantity_in_stock = quantity_in_stock - %s,
                    last_restocked_date = NOW()
                WHERE product_id = %s
            """, (item['quantity'], item['product_id']))
            
            # Log stock deduction
            cursor.execute("""
                INSERT INTO stock_logs (product_id, quantity_changed, log_type, reason, logged_by)
                VALUES (%s, %s, 'deduction', %s, %s)
            """, (item['product_id'], -item['quantity'], 
                  f"Order #{order['order_number']} approved", session['user_id']))
        
        # Update order status
        cursor.execute("""
            UPDATE orders 
            SET status = 'approved', 
                approved_by = %s, 
                approved_at = NOW()
            WHERE order_id = %s
        """, (session['user_id'], order_id))
        
        mysql.connection.commit()
        cursor.close()
        
        flash(f'Order #{order["order_number"]} approved successfully! Stock has been deducted.', 'success')
        
    except Exception as e:
        mysql.connection.rollback()
        import traceback
        print(f"Approve order error: {str(e)}")
        traceback.print_exc()
        flash('Error approving order', 'danger')
    
    return redirect(url_for('manage_orders'))

@app.route('/orders/reject/<int:order_id>')
def reject_order(order_id):
    """Cancel/reject an order"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            UPDATE orders 
            SET status = 'cancelled'
            WHERE order_id = %s
        """, (order_id,))
        
        mysql.connection.commit()
        cursor.close()
        
        flash('Order cancelled successfully!', 'success')
        
    except Exception as e:
        print(f"Reject order error: {str(e)}")
        flash('Error cancelling order', 'danger')
    
    return redirect(url_for('manage_orders'))


@app.route('/orders/update-status/<int:order_id>/<status>')
def update_order_status(order_id, status):
    """Update order status"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    valid_statuses = ['approved', 'packed', 'dispatched', 'delivered', 'cancelled']
    
    if status not in valid_statuses:
        flash('Invalid status', 'danger')
        return redirect(url_for('manage_orders'))
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            UPDATE orders 
            SET status = %s
            WHERE order_id = %s
        """, (status, order_id))
        
        mysql.connection.commit()
        cursor.close()
        
        flash(f'Order status updated to {status}!', 'success')
        
    except Exception as e:
        print(f"Update order status error: {str(e)}")
        flash('Error updating order status', 'danger')
    
    return redirect(url_for('manage_orders'))

@app.route('/orders/repeat/<int:order_id>', methods=['POST'])
def repeat_order(order_id):
    """Repeat a previous order"""
    if 'user_id' not in session or session.get('role') != 'client':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Verify order belongs to this client
        cursor.execute("""
            SELECT o.order_id FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            WHERE o.order_id = %s AND c.user_id = %s
        """, (order_id, session['user_id']))
        
        if not cursor.fetchone():
            flash('Order not found', 'danger')
            cursor.close()
            return redirect(url_for('my_orders'))
        
        # Get order items
        cursor.execute("""
            SELECT oi.product_id, oi.quantity, p.product_name, p.is_active
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        
        items = cursor.fetchall()
        cursor.close()
        
        if not items:
            flash('No items found in this order', 'warning')
            return redirect(url_for('my_orders'))
        
        # Store items in session
        repeat_items = {}
        inactive_products = []
        
        for item in items:
            if item['is_active']:
                repeat_items[str(item['product_id'])] = item['quantity']
            else:
                inactive_products.append(item['product_name'])
        
        session['repeat_order_items'] = repeat_items
        session.modified = True
        
        if inactive_products:
            flash(f'Note: Some products are no longer available: {", ".join(inactive_products)}', 'warning')
        
        flash(f'Order items loaded! Review and place your order.', 'success')
        return redirect(url_for('place_order'))
        
    except Exception as e:
        print(f"Repeat order error: {str(e)}")
        flash('Error repeating order', 'danger')
        return redirect(url_for('my_orders'))

@app.route('/feedback/submit', methods=['POST'])
def submit_feedback():
    """Submit feedback for a delivered order"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    if session.get('role') != 'client':
        return jsonify({'success': False, 'message': 'Only clients can submit feedback'}), 403
    
    try:
        # Get JSON data
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        order_id = data.get('order_id')
        rating = data.get('rating')
        comments = data.get('comments', '').strip()
        
        # Validate inputs
        if not order_id:
            return jsonify({'success': False, 'message': 'Order ID is required'}), 400
        
        if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Valid rating (1-5) is required'}), 400
        
        cursor = mysql.connection.cursor()
        
        # Get client_id
        cursor.execute("SELECT client_id FROM clients WHERE user_id = %s", (session['user_id'],))
        client = cursor.fetchone()
        
        if not client:
            cursor.close()
            return jsonify({'success': False, 'message': 'Client not found'}), 404
        
        client_id = client['client_id']
        
        # Verify order belongs to this client and is delivered
        cursor.execute("""
            SELECT order_id FROM orders 
            WHERE order_id = %s AND client_id = %s AND status = 'delivered'
        """, (order_id, client_id))
        
        order = cursor.fetchone()
        
        if not order:
            cursor.close()
            return jsonify({'success': False, 'message': 'Order not found or not delivered'}), 404
        
        # Check if feedback already exists
        cursor.execute("""
            SELECT feedback_id FROM feedback 
            WHERE order_id = %s AND client_id = %s
        """, (order_id, client_id))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing feedback
            cursor.execute("""
                UPDATE feedback 
                SET rating = %s, comments = %s, created_at = NOW()
                WHERE feedback_id = %s
            """, (rating, comments, existing['feedback_id']))
            message = 'Feedback updated successfully!'
        else:
            # Insert new feedback
            cursor.execute("""
                INSERT INTO feedback (order_id, client_id, rating, comments)
                VALUES (%s, %s, %s, %s)
            """, (order_id, client_id, rating, comments))
            message = 'Feedback submitted successfully!'
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({'success': True, 'message': message}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        import traceback
        print(f"Feedback submission error: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500
# ================================================
# INVENTORY MANAGEMENT ROUTES
# Add these routes to your app.py file after the order routes
# ================================================

@app.route('/inventory')
def inventory():
    """View inventory/stock levels"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get all inventory with product details
        cursor.execute("""
            SELECT i.*, p.product_name, p.unit_price, p.packaging_size, c.category_name
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.is_active = TRUE
            ORDER BY p.product_name
        """)
        inventory = cursor.fetchall()
        
        # Calculate statistics
        low_stock_count = 0
        out_of_stock_count = 0
        total_value = 0.0
        
        for item in inventory:
            if item['quantity_in_stock'] == 0:
                out_of_stock_count += 1
            elif item['quantity_in_stock'] <= item['minimum_stock_level']:
                low_stock_count += 1
            
            total_value += float(item['quantity_in_stock']) * float(item['unit_price'])
        
        cursor.close()
        
        return render_template('inventory.html',
                             inventory=inventory,
                             low_stock_count=low_stock_count,
                             out_of_stock_count=out_of_stock_count,
                             total_value=total_value)
        
    except Exception as e:
        print(f"Inventory error: {str(e)}")
        flash('Error loading inventory', 'danger')
        return render_template('inventory.html',
                             inventory=[],
                             low_stock_count=0,
                             out_of_stock_count=0,
                             total_value=0)


@app.route('/inventory/update-stock', methods=['POST'])
def update_stock():
    """Update stock quantity"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('inventory'))
    
    try:
        product_id = request.form.get('product_id')
        action_type = request.form.get('action_type')  # addition, deduction, adjustment
        quantity = int(request.form.get('quantity', 0))
        reason = request.form.get('reason', '')
        
        if quantity <= 0 and action_type != 'adjustment':
            flash('Quantity must be greater than 0', 'danger')
            return redirect(url_for('inventory'))
        
        cursor = mysql.connection.cursor()
        
        # Get current stock
        cursor.execute("SELECT quantity_in_stock FROM inventory WHERE product_id = %s", (product_id,))
        current = cursor.fetchone()
        
        if not current:
            flash('Product not found in inventory', 'danger')
            return redirect(url_for('inventory'))
        
        current_stock = current['quantity_in_stock']
        new_stock = current_stock
        quantity_changed = quantity
        
        # Calculate new stock based on action type
        if action_type == 'addition':
            new_stock = current_stock + quantity
        elif action_type == 'deduction':
            if quantity > current_stock:
                flash('Cannot remove more stock than available', 'danger')
                return redirect(url_for('inventory'))
            new_stock = current_stock - quantity
            quantity_changed = -quantity
        elif action_type == 'adjustment':
            new_stock = quantity
            quantity_changed = quantity - current_stock
        
        # Update inventory
        cursor.execute("""
            UPDATE inventory 
            SET quantity_in_stock = %s, 
                last_restocked_date = NOW()
            WHERE product_id = %s
        """, (new_stock, product_id))
        
        # Log the stock change
        cursor.execute("""
            INSERT INTO stock_logs (product_id, quantity_changed, log_type, reason, logged_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (product_id, quantity_changed, action_type, reason, session['user_id']))
        
        mysql.connection.commit()
        cursor.close()
        
        flash('Stock updated successfully!', 'success')
        return redirect(url_for('inventory'))
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Update stock error: {str(e)}")
        flash('Error updating stock', 'danger')
        return redirect(url_for('inventory'))


@app.route('/inventory/history/<int:product_id>')
def stock_history(product_id):
    """View stock history for a product"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('inventory'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get product details
        cursor.execute("""
            SELECT p.*, c.category_name, i.quantity_in_stock
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            JOIN inventory i ON p.product_id = i.product_id
            WHERE p.product_id = %s
        """, (product_id,))
        product = cursor.fetchone()
        
        if not product:
            flash('Product not found', 'danger')
            return redirect(url_for('inventory'))
        
        # Get stock logs
        cursor.execute("""
            SELECT sl.*, u.username, u.first_name, u.last_name
            FROM stock_logs sl
            JOIN users u ON sl.logged_by = u.user_id
            WHERE sl.product_id = %s
            ORDER BY sl.created_at DESC
        """, (product_id,))
        logs = cursor.fetchall()
        
        cursor.close()
        
        return render_template('stock_history.html',
                             product=product,
                             logs=logs)
        
    except Exception as e:
        print(f"Stock history error: {str(e)}")
        flash('Error loading stock history', 'danger')
        return redirect(url_for('inventory'))

@app.route('/clients')
def clients():
    """View all clients - for admin/staff"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get all clients with user details
        cursor.execute("""
            SELECT c.*, u.is_active, u.username
            FROM clients c
            JOIN users u ON c.user_id = u.user_id
            ORDER BY c.organization_name
        """)
        clients = cursor.fetchall()
        
        # Get order statistics for each client
        for client in clients:
            # Total orders
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM orders
                WHERE client_id = %s
            """, (client['client_id'],))
            client['total_orders'] = cursor.fetchone()['count']
            
            # Pending orders
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM orders
                WHERE client_id = %s AND status = 'pending'
            """, (client['client_id'],))
            client['pending_orders'] = cursor.fetchone()['count']
            
            # Total spent
            cursor.execute("""
                SELECT COALESCE(SUM(grand_total), 0) as total
                FROM orders
                WHERE client_id = %s AND status != 'cancelled'
            """, (client['client_id'],))
            client['total_spent'] = float(cursor.fetchone()['total'])
        
        # Calculate overall statistics
        active_count = sum(1 for c in clients if c['is_active'])
        total_orders = sum(c['total_orders'] for c in clients)
        total_revenue = sum(c['total_spent'] for c in clients)
        
        cursor.close()
        
        return render_template('clients.html',
                             clients=clients,
                             active_count=active_count,
                             total_orders=total_orders,
                             total_revenue=total_revenue)
        
    except Exception as e:
        import traceback
        print(f"Clients error: {str(e)}")
        traceback.print_exc()
        
        flash('Error loading clients', 'danger')
        return render_template('clients.html',
                             clients=[],
                             active_count=0,
                             total_orders=0,
                             total_revenue=0)


@app.route('/clients/<int:client_id>/orders')
def client_orders(client_id):
    """View all orders for a specific client - for admin/staff"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get client details
        cursor.execute("""
            SELECT c.*, u.username
            FROM clients c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.client_id = %s
        """, (client_id,))
        client = cursor.fetchone()
        
        if not client:
            flash('Client not found', 'danger')
            return redirect(url_for('clients'))
        
        # Get all orders for this client
        cursor.execute("""
            SELECT o.*
            FROM orders o
            WHERE o.client_id = %s
            ORDER BY o.order_date DESC
        """, (client_id,))
        orders = cursor.fetchall()
        
        # Get order items for each order
        for order in orders:
            cursor.execute("""
                SELECT oi.*, p.product_name
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                WHERE oi.order_id = %s
            """, (order['order_id'],))
            order['order_items'] = cursor.fetchall()
        
        # Calculate statistics
        pending_count = 0
        delivered_count = 0
        total_revenue = 0.0
        
        for o in orders:
            if o['status'] == 'pending':
                pending_count += 1
            if o['status'] == 'delivered':
                delivered_count += 1
            if o['status'] != 'cancelled':
                total_revenue += float(o['grand_total'])
        
        cursor.close()
        
        return render_template('client_orders.html',
                             client=client,
                             orders=orders,
                             pending_count=pending_count,
                             delivered_count=delivered_count,
                             total_revenue=total_revenue)
        
    except Exception as e:
        import traceback
        print(f"Client orders error: {str(e)}")
        traceback.print_exc()
        
        flash('Error loading client orders', 'danger')
        return redirect(url_for('clients'))

@app.route('/reports')
def reports():
    """Reports & Analytics for admin/staff"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))

    try:
        cursor = mysql.connection.cursor()

        # ---- KEY SUMMARY STATS ----

        # Total orders
        cursor.execute("SELECT COUNT(*) as count FROM orders")
        total_orders = cursor.fetchone()['count']

        # Total revenue (non-cancelled)
        cursor.execute("SELECT COALESCE(SUM(grand_total), 0) as total FROM orders WHERE status != 'cancelled'")
        total_revenue = float(cursor.fetchone()['total'])

        # Total clients
        cursor.execute("SELECT COUNT(*) as count FROM clients")
        total_clients = cursor.fetchone()['count']

        # Total active products
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE is_active = TRUE")
        total_products = cursor.fetchone()['count']

        # This month orders
        cursor.execute("""
            SELECT COUNT(*) as count FROM orders
            WHERE MONTH(order_date) = MONTH(NOW())
            AND YEAR(order_date) = YEAR(NOW())
        """)
        this_month_orders = cursor.fetchone()['count']

        # This month revenue
        cursor.execute("""
            SELECT COALESCE(SUM(grand_total), 0) as total FROM orders
            WHERE MONTH(order_date) = MONTH(NOW())
            AND YEAR(order_date) = YEAR(NOW())
            AND status != 'cancelled'
        """)
        this_month_revenue = float(cursor.fetchone()['total'])

        # ---- ORDERS BY STATUS ----
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM orders
            GROUP BY status
            ORDER BY FIELD(status, 'pending', 'approved', 'packed', 'dispatched', 'delivered', 'cancelled')
        """)
        order_by_status = cursor.fetchall()

        # ---- MONTHLY REVENUE (Last 6 Months) ----
        monthly_revenue = []
        for i in range(5, -1, -1):
            date = datetime.now() - timedelta(days=i * 30)
            month_num = date.month
            year_num = date.year
            month_name = calendar.month_abbr[month_num]

            cursor.execute("""
                SELECT COALESCE(SUM(grand_total), 0) as revenue
                FROM orders
                WHERE MONTH(order_date) = %s
                AND YEAR(order_date) = %s
                AND status != 'cancelled'
            """, (month_num, year_num))

            revenue = float(cursor.fetchone()['revenue'])
            monthly_revenue.append({
                'month_name': f"{month_name} {year_num}",
                'revenue': revenue
            })

        # ---- MONTHLY ORDERS (Last 6 Months) ----
        monthly_orders = []
        for i in range(5, -1, -1):
            date = datetime.now() - timedelta(days=i * 30)
            month_num = date.month
            year_num = date.year
            month_name = calendar.month_abbr[month_num]

            cursor.execute("""
                SELECT COUNT(*) as order_count
                FROM orders
                WHERE MONTH(order_date) = %s
                AND YEAR(order_date) = %s
            """, (month_num, year_num))

            order_count = cursor.fetchone()['order_count']
            monthly_orders.append({
                'month_name': f"{month_name} {year_num}",
                'order_count': order_count
            })

        # ---- TOP SELLING PRODUCTS ----
        cursor.execute("""
            SELECT p.product_name,
                   SUM(oi.quantity) as total_quantity,
                   SUM(oi.total_price) as total_revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.status != 'cancelled'
            GROUP BY p.product_id, p.product_name
            ORDER BY total_quantity DESC
            LIMIT 5
        """)
        top_products = cursor.fetchall()

        # ---- TOP CLIENTS BY REVENUE ----
        cursor.execute("""
            SELECT c.organization_name,
                   COALESCE(SUM(o.grand_total), 0) as total_spent,
                   COUNT(o.order_id) as order_count
            FROM clients c
            LEFT JOIN orders o ON c.client_id = o.client_id AND o.status != 'cancelled'
            GROUP BY c.client_id, c.organization_name
            ORDER BY total_spent DESC
            LIMIT 5
        """)
        top_clients = cursor.fetchall()

        # ---- LOW STOCK PRODUCTS ----
        cursor.execute("""
            SELECT p.product_name, i.quantity_in_stock, i.minimum_stock_level
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            WHERE i.quantity_in_stock <= i.minimum_stock_level
            AND p.is_active = TRUE
            ORDER BY i.quantity_in_stock ASC
        """)
        low_stock_products = cursor.fetchall()

        cursor.close()

        return render_template('reports.html',
                             total_orders=total_orders,
                             total_revenue=total_revenue,
                             total_clients=total_clients,
                             total_products=total_products,
                             this_month_orders=this_month_orders,
                             this_month_revenue=this_month_revenue,
                             order_by_status=order_by_status,
                             monthly_revenue=monthly_revenue,
                             monthly_orders=monthly_orders,
                             top_products=top_products,
                             top_clients=top_clients,
                             low_stock_products=low_stock_products)

    except Exception as e:
        import traceback
        print(f"Reports error: {str(e)}")
        traceback.print_exc()
        flash('Error loading reports', 'danger')
        return render_template('reports.html',
                             total_orders=0,
                             total_revenue=0,
                             total_clients=0,
                             total_products=0,
                             this_month_orders=0,
                             this_month_revenue=0,
                             order_by_status=[],
                             monthly_revenue=[],
                             monthly_orders=[],
                             top_products=[],
                             top_clients=[],
                             low_stock_products=[])

@app.route('/invoice/generate/<int:order_id>')
def generate_invoice(order_id):
    """Generate PDF invoice for an order"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get order details with client info
        cursor.execute("""
            SELECT o.*, c.organization_name, c.contact_person, c.contact_email, 
                   c.contact_phone, c.address, c.city, c.state, c.pincode,
                   c.gst_number
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            WHERE o.order_id = %s
        """, (order_id,))
        order = cursor.fetchone()
        
        if not order:
            flash('Order not found', 'danger')
            return redirect(url_for('manage_orders' if session.get('role') in ['admin', 'staff'] else 'my_orders'))
        
        # Check access - clients can only see their own invoices
        if session.get('role') == 'client':
            cursor.execute("""
                SELECT c.client_id FROM clients c
                JOIN orders o ON c.client_id = o.client_id
                WHERE o.order_id = %s AND c.user_id = %s
            """, (order_id, session['user_id']))
            if not cursor.fetchone():
                flash('Access denied', 'danger')
                return redirect(url_for('my_orders'))
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, p.product_name, p.packaging_size
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        items = cursor.fetchall()
        
        cursor.close()
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#3a662c'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#3a662c'),
            spaceAfter=12
        )
        
        # ========== UPDATED: Company Header with Logo ==========
        import os
        logo_path_png = os.path.join(app.static_folder, 'images', 'RBLOGO.png')
        logo_path_svg = os.path.join(app.static_folder, 'images', 'RBLOGO.svg')
        
        logo_added = False
        
        # Try PNG first (works better in PDFs), then SVG
        for logo_path in [logo_path_png, logo_path_svg]:
            if os.path.exists(logo_path):
                try:
                    # Create logo image - SMALLER SIZE (0.8 inch instead of 1.2)
                    logo_img = Image(logo_path, width=0.8*inch, height=0.4*inch)
                    
                    # Create company info text
                    company_info = Paragraph("""
                    <para align=left>
                    <b><font size=20 color="#3a662c">ROYAL BEVERAGES</font></b><br/>
                    <font size=10>Supply & Distribution Management</font><br/>
                    <font size=8>GSTIN: 27CUZPS1971H1ZP</font>
                    </para>
                    """, styles['Normal'])
                    
                    # Create header table with logo and company info side by side
                    header_data = [[logo_img, company_info]]
                    header_table = Table(header_data, colWidths=[1*inch, 5*inch])
                    header_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 0),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ]))
                    elements.append(header_table)
                    elements.append(Spacer(1, 20))
                    logo_added = True
                    break
                except Exception as e:
                    print(f"Logo error ({logo_path}): {e}")
                    continue
        
        # Fallback to text only if logo couldn't be loaded
        if not logo_added:
            elements.append(Paragraph("ROYAL BEVERAGES", title_style))
            elements.append(Paragraph("Supply & Distribution Management", styles['Normal']))
            elements.append(Paragraph("GSTIN: 27CUZPS1971H1ZP", styles['Normal']))
            elements.append(Spacer(1, 12))
        # ========== END LOGO SECTION ==========
        
        # Invoice Title
        elements.append(Paragraph("TAX INVOICE", heading_style))
        elements.append(Spacer(1, 12))
        
        # Invoice Details
        invoice_data = [
            ['Invoice Number:', order['order_number']],
            ['Invoice Date:', order['order_date'].strftime('%d %b %Y')],
            ['Order Status:', order['status'].upper()],
        ]
        
        invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
        invoice_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(invoice_table)
        elements.append(Spacer(1, 20))
        
        # Bill To Section
        elements.append(Paragraph("BILL TO:", heading_style))
        
        # Build bill to text with optional GST
        bill_to_parts = [
            f"<b>{order['organization_name']}</b>",
            order['contact_person'],
            order['address'],
            f"{order['city']}, {order['state']} - {order['pincode']}",
            f"Phone: {order['contact_phone']}",
            f"Email: {order['contact_email']}"
        ]
        
        # Add GST if available
        if order.get('gst_number'):
            bill_to_parts.append(f"GSTIN: {order['gst_number']}")
        
        bill_to_text = "<br/>".join(bill_to_parts)
        elements.append(Paragraph(bill_to_text, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Items Table
        elements.append(Paragraph("ORDER DETAILS:", heading_style))
        
        # Table header
        table_data = [['Sr.', 'Product', 'Packaging', 'Qty', 'Rate', 'GST%', 'Amount']]
        
        # Add items
        for i, item in enumerate(items, 1):
            table_data.append([
                str(i),
                item['product_name'],
                item['packaging_size'],
                str(item['quantity']),
                f"Rs.{item['unit_price']:.2f}",
                f"{item['gst_percentage']:.0f}%",
                f"Rs.{item['total_price']:.2f}"
            ])
        
        # Create table
        items_table = Table(table_data, colWidths=[0.5*inch, 2*inch, 1*inch, 0.7*inch, 1*inch, 0.7*inch, 1.1*inch])
        items_table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3a662c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Body style
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Product name left aligned
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 20))
        
        # Summary Table
        summary_data = [
            ['Subtotal:', f"Rs.{order['total_amount']:.2f}"],
            ['GST Amount:', f"Rs.{order['gst_amount']:.2f}"],
            ['', ''],
            ['TOTAL AMOUNT:', f"Rs.{order['grand_total']:.2f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[4.5*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 2), 'Helvetica'),
            ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 2), 10),
            ('FONTSIZE', (0, 3), (-1, 3), 12),
            ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#3a662c')),
            ('LINEABOVE', (0, 3), (-1, 3), 2, colors.HexColor('#3a662c')),
            ('TOPPADDING', (0, 3), (-1, 3), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 30))
        
        # Footer
        footer_text = """
        <para align=center>
        <b>Thank you for your business!</b><br/>
        For any queries, please contact us at support@royalbeverages.com<br/>
        This is a computer-generated invoice and does not require a signature.
        </para>
        """
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF from buffer
        buffer.seek(0)
        
        # Send file
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Invoice_{order["order_number"]}.pdf'
        )
        
    except Exception as e:
        import traceback
        print(f"Invoice generation error: {str(e)}")
        traceback.print_exc()
        
        flash('Error generating invoice', 'danger')
        return redirect(url_for('manage_orders' if session.get('role') in ['admin', 'staff'] else 'my_orders'))

@app.route('/profile')
def profile():
    """View user profile"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        cursor = mysql.connection.cursor()

        # Get user details
        cursor.execute("""
            SELECT user_id, username, email, first_name, last_name,
                   phone, role, is_active, created_at
            FROM users
            WHERE user_id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()

        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('login'))

        # Get client details if role is client
        client = None
        activity = {'total_orders': 0, 'total_spent': 0.0, 'pending_orders': 0}

        if session.get('role') == 'client':
            cursor.execute("""
                SELECT * FROM clients WHERE user_id = %s
            """, (session['user_id'],))
            client = cursor.fetchone()

            if client:
                # Get activity stats
                cursor.execute("""
                    SELECT COUNT(*) as count FROM orders
                    WHERE client_id = %s
                """, (client['client_id'],))
                activity['total_orders'] = cursor.fetchone()['count']

                cursor.execute("""
                    SELECT COALESCE(SUM(grand_total), 0) as total
                    FROM orders
                    WHERE client_id = %s AND status != 'cancelled'
                """, (client['client_id'],))
                activity['total_spent'] = float(cursor.fetchone()['total'])

                cursor.execute("""
                    SELECT COUNT(*) as count FROM orders
                    WHERE client_id = %s AND status = 'pending'
                """, (client['client_id'],))
                activity['pending_orders'] = cursor.fetchone()['count']

        cursor.close()

        return render_template('profile.html',
                             user=user,
                             client=client,
                             activity=activity)

    except Exception as e:
        import traceback
        print(f"Profile error: {str(e)}")
        traceback.print_exc()
        flash('Error loading profile', 'danger')
        return redirect(url_for('dashboard') if session.get('role') in ['admin', 'staff'] else url_for('client_dashboard'))


@app.route('/profile/update', methods=['POST'])
def update_profile():
    """Update user profile"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    form_type = request.form.get('form_type')

    try:
        cursor = mysql.connection.cursor()

        # ---- UPDATE PERSONAL INFO ----
        if form_type == 'personal_info':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()

            if not first_name or not last_name or not email:
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('profile'))

            # Check if email is already taken by another user
            cursor.execute("""
                SELECT user_id FROM users
                WHERE email = %s AND user_id != %s
            """, (email, session['user_id']))

            if cursor.fetchone():
                flash('Email address is already in use', 'danger')
                cursor.close()
                return redirect(url_for('profile'))

            cursor.execute("""
                UPDATE users
                SET first_name = %s, last_name = %s, email = %s, phone = %s
                WHERE user_id = %s
            """, (first_name, last_name, email, phone, session['user_id']))

            mysql.connection.commit()
            
            # Update session
            session['first_name'] = first_name
            session['last_name'] = last_name
            
            flash('Personal information updated successfully!', 'success')

        # ---- CHANGE PASSWORD ----
        elif form_type == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not current_password or not new_password or not confirm_password:
                flash('Please fill in all password fields', 'danger')
                cursor.close()
                return redirect(url_for('profile'))

            if new_password != confirm_password:
                flash('New passwords do not match', 'danger')
                cursor.close()
                return redirect(url_for('profile'))

            # Validate new password strength (same as signup)
            if len(new_password) < 8:
                flash('Password must be at least 8 characters', 'danger')
                cursor.close()
                return redirect(url_for('profile'))
            
            if not re.search(r'[A-Z]', new_password):
                flash('Password must contain at least one uppercase letter', 'danger')
                cursor.close()
                return redirect(url_for('profile'))
            
            if not re.search(r'[a-z]', new_password):
                flash('Password must contain at least one lowercase letter', 'danger')
                cursor.close()
                return redirect(url_for('profile'))
            
            if not re.search(r'[0-9]', new_password):
                flash('Password must contain at least one number', 'danger')
                cursor.close()
                return redirect(url_for('profile'))
            
            if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', new_password):
                flash('Password must contain at least one special character', 'danger')
                cursor.close()
                return redirect(url_for('profile'))

            # Verify current password
            cursor.execute("""
                SELECT password_hash FROM users WHERE user_id = %s
            """, (session['user_id'],))
            user = cursor.fetchone()

            from werkzeug.security import check_password_hash, generate_password_hash

            if not check_password_hash(user['password_hash'], current_password):
                flash('Current password is incorrect', 'danger')
                cursor.close()
                return redirect(url_for('profile'))

            # Hash new password
            new_password_hash = generate_password_hash(new_password)

            cursor.execute("""
                UPDATE users SET password_hash = %s WHERE user_id = %s
            """, (new_password_hash, session['user_id']))

            mysql.connection.commit()
            flash('Password updated successfully!', 'success')

        # ---- UPDATE BUSINESS INFO (Client Only) ----
        elif form_type == 'business_info':
            if session.get('role') != 'client':
                flash('Access denied', 'danger')
                cursor.close()
                return redirect(url_for('profile'))

            organization_name = request.form.get('organization_name', '').strip()
            contact_person = request.form.get('contact_person', '').strip()
            contact_phone = request.form.get('contact_phone', '').strip()
            contact_email = request.form.get('contact_email', '').strip()
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            state = request.form.get('state', '').strip()
            pincode = request.form.get('pincode', '').strip()
            gst_number = request.form.get('gst_number', '').strip()

            if not all([organization_name, contact_person, contact_phone,
                       contact_email, address, city, state, pincode]):
                flash('Please fill in all required fields', 'danger')
                cursor.close()
                return redirect(url_for('profile'))

            cursor.execute("""
                UPDATE clients
                SET organization_name = %s, contact_person = %s,
                    contact_phone = %s, contact_email = %s,
                    address = %s, city = %s, state = %s,
                    pincode = %s, gst_number = %s
                WHERE user_id = %s
            """, (organization_name, contact_person, contact_phone,
                  contact_email, address, city, state, pincode,
                  gst_number, session['user_id']))

            mysql.connection.commit()
            flash('Business information updated successfully!', 'success')

        cursor.close()

    except Exception as e:
        mysql.connection.rollback()
        import traceback
        print(f"Update profile error: {str(e)}")
        traceback.print_exc()
        flash('Error updating profile. Please try again.', 'danger')

    return redirect(url_for('profile'))

@app.route('/delivery')
def delivery():
    """Delivery management page for admin/staff"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('client_dashboard'))

    try:
        cursor = mysql.connection.cursor()

        # Get all orders that are packed, dispatched or delivered
        cursor.execute("""
            SELECT o.*, 
                   c.organization_name, c.contact_person, c.contact_phone,
                   c.address, c.city, c.state, c.pincode,
                   CONCAT(u.first_name, ' ', u.last_name) as delivery_person_name
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            LEFT JOIN users u ON o.delivery_person_id = u.user_id
            WHERE o.status IN ('packed', 'dispatched', 'delivered')
            ORDER BY 
                FIELD(o.status, 'packed', 'dispatched', 'delivered'),
                o.order_date DESC
        """)
        orders = cursor.fetchall()

        # Get delivery staff (admin and staff users)
        cursor.execute("""
            SELECT user_id, first_name, last_name, username
            FROM users
            WHERE role IN ('admin', 'staff') AND is_active = TRUE
            ORDER BY first_name
        """)
        delivery_staff = cursor.fetchall()

        # Statistics
        cursor.execute("""
            SELECT COUNT(*) as count FROM orders WHERE status = 'packed'
        """)
        packed_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM orders WHERE status = 'dispatched'
        """)
        dispatched_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM orders 
            WHERE status = 'delivered' AND DATE(approved_at) = CURDATE()
        """)
        delivered_today = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM orders WHERE status = 'delivered'
        """)
        total_delivered = cursor.fetchone()['count']

        cursor.close()

        return render_template('delivery.html',
                             orders=orders,
                             delivery_staff=delivery_staff,
                             packed_count=packed_count,
                             dispatched_count=dispatched_count,
                             delivered_today=delivered_today,
                             total_delivered=total_delivered)

    except Exception as e:
        import traceback
        print(f"Delivery error: {str(e)}")
        traceback.print_exc()
        flash('Error loading delivery page', 'danger')
        return render_template('delivery.html',
                             orders=[],
                             delivery_staff=[],
                             packed_count=0,
                             dispatched_count=0,
                             delivered_today=0,
                             total_delivered=0)


@app.route('/delivery/assign', methods=['POST'])
def assign_delivery():
    """Assign delivery person and dispatch order"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('delivery'))

    try:
        order_id = request.form.get('order_id')
        delivery_person = request.form.get('delivery_person')
        delivery_notes = request.form.get('delivery_notes', '')

        if not order_id or not delivery_person:
            flash('Please select a delivery person', 'danger')
            return redirect(url_for('delivery'))

        cursor = mysql.connection.cursor()

        # Update order - assign delivery person and change status to dispatched
        cursor.execute("""
            UPDATE orders
            SET status = 'dispatched',
                delivery_person_id = %s,
                delivery_notes = %s,
                dispatched_at = NOW()
            WHERE order_id = %s AND status = 'packed'
        """, (delivery_person, delivery_notes, order_id))

        mysql.connection.commit()
        cursor.close()

        flash('Order assigned and dispatched successfully!', 'success')

    except Exception as e:
        mysql.connection.rollback()
        import traceback
        print(f"Assign delivery error: {str(e)}")
        traceback.print_exc()
        flash('Error assigning delivery', 'danger')

    return redirect(url_for('delivery'))


@app.route('/delivery/mark-delivered', methods=['POST'])
def mark_delivered():
    """Mark order as delivered"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['admin', 'staff']:
        flash('Access denied', 'danger')
        return redirect(url_for('delivery'))

    try:
        order_id = request.form.get('order_id')
        delivery_notes = request.form.get('delivery_notes', '')

        cursor = mysql.connection.cursor()

        # Update order status to delivered
        cursor.execute("""
            UPDATE orders
            SET status = 'delivered',
                delivery_notes = %s,
                delivered_at = NOW()
            WHERE order_id = %s AND status = 'dispatched'
        """, (delivery_notes, order_id))

        mysql.connection.commit()
        cursor.close()

        flash('Order marked as delivered successfully!', 'success')

    except Exception as e:
        mysql.connection.rollback()
        import traceback
        print(f"Mark delivered error: {str(e)}")
        traceback.print_exc()
        flash('Error marking order as delivered', 'danger')

    return redirect(url_for('delivery'))

@app.route('/browse-products')
def browse_products():
    """Browse products catalog - FOR CLIENTS (read-only)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Only allow clients
    if session.get('role') != 'client':
        flash('Use the Products page for management', 'info')
        return redirect(url_for('products'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get only active products for clients
        cursor.execute("""
            SELECT p.*, c.category_name 
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.is_active = TRUE
            ORDER BY c.category_name, p.product_name
        """)
        products = cursor.fetchall()
        
        cursor.execute("SELECT * FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        
        cursor.close()
        
        return render_template('browse_products.html', 
                             products=products,
                             categories=categories)
        
    except Exception as e:
        print(f"Browse products error: {str(e)}")
        flash('Error loading products', 'danger')
        return redirect(url_for('client_dashboard'))


# Product detail route (already exists - just verify it's there)
@app.route('/products/<int:product_id>')
def product_detail(product_id):
    """Product detail page - accessible to all logged-in users"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            SELECT p.*, c.category_name 
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.product_id = %s
        """, (product_id,))
        
        product = cursor.fetchone()
        cursor.close()
        
        if not product:
            flash('Product not found', 'danger')
            return redirect(url_for('browse_products' if session.get('role') == 'client' else 'products'))
        
        return render_template('product_detail.html', product=product)
        
    except Exception as e:
        print(f"Product detail error: {str(e)}")
        flash('Error loading product', 'danger')
        return redirect(url_for('browse_products' if session.get('role') == 'client' else 'products'))


@app.route('/chat')
def chat_list():
    """List all conversations - Admin sees all clients, Client sees admin only"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        if session.get('role') in ['admin', 'staff']:
            # Admin: Get all clients with latest message
            cursor.execute("""
                SELECT DISTINCT
                    u.user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    c.organization_name,
                    (SELECT COUNT(*) 
                     FROM messages 
                     WHERE sender_id = u.user_id 
                       AND receiver_id = %s 
                       AND is_read = FALSE) as unread_count,
                    (SELECT message_text 
                     FROM messages 
                     WHERE (sender_id = u.user_id AND receiver_id = %s)
                        OR (sender_id = %s AND receiver_id = u.user_id)
                     ORDER BY created_at DESC LIMIT 1) as last_message,
                    (SELECT created_at 
                     FROM messages 
                     WHERE (sender_id = u.user_id AND receiver_id = %s)
                        OR (sender_id = %s AND receiver_id = u.user_id)
                     ORDER BY created_at DESC LIMIT 1) as last_message_time
                FROM users u
                JOIN clients c ON u.user_id = c.user_id
                WHERE u.role = 'client' AND u.is_active = TRUE
                ORDER BY last_message_time DESC
            """, (session['user_id'], session['user_id'], session['user_id'], 
                  session['user_id'], session['user_id']))
            
            conversations = cursor.fetchall()
            
        else:
            # Client: Get admin contact
            cursor.execute("""
                SELECT 
                    u.user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    'Royal Beverages Support' as organization_name,
                    (SELECT COUNT(*) 
                     FROM messages 
                     WHERE sender_id = u.user_id 
                       AND receiver_id = %s 
                       AND is_read = FALSE) as unread_count,
                    (SELECT message_text 
                     FROM messages 
                     WHERE (sender_id = u.user_id AND receiver_id = %s)
                        OR (sender_id = %s AND receiver_id = u.user_id)
                     ORDER BY created_at DESC LIMIT 1) as last_message,
                    (SELECT created_at 
                     FROM messages 
                     WHERE (sender_id = u.user_id AND receiver_id = %s)
                        OR (sender_id = %s AND receiver_id = u.user_id)
                     ORDER BY created_at DESC LIMIT 1) as last_message_time
                FROM users u
                WHERE u.role = 'admin' AND u.is_active = TRUE
                LIMIT 1
            """, (session['user_id'], session['user_id'], session['user_id'],
                  session['user_id'], session['user_id']))
            
            admin = cursor.fetchone()
            conversations = [admin] if admin else []
        
        cursor.close()
        
        return render_template('chat_list.html', conversations=conversations)
        
    except Exception as e:
        print(f"Chat list error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error loading conversations', 'danger')
        return redirect(url_for('dashboard' if session.get('role') in ['admin', 'staff'] else 'client_dashboard'))


@app.route('/chat/<int:user_id>')
def chat_conversation(user_id):
    """View conversation with a specific user"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get other user's info
        cursor.execute("""
            SELECT u.user_id, u.username, u.first_name, u.last_name, u.role,
                   c.organization_name
            FROM users u
            LEFT JOIN clients c ON u.user_id = c.user_id
            WHERE u.user_id = %s
        """, (user_id,))
        
        other_user = cursor.fetchone()
        
        if not other_user:
            flash('User not found', 'danger')
            return redirect(url_for('chat_list'))
        
        # Get all messages in conversation
        cursor.execute("""
            SELECT m.*, 
                   sender.first_name as sender_first_name,
                   sender.last_name as sender_last_name
            FROM messages m
            JOIN users sender ON m.sender_id = sender.user_id
            WHERE (m.sender_id = %s AND m.receiver_id = %s)
               OR (m.sender_id = %s AND m.receiver_id = %s)
            ORDER BY m.created_at ASC
        """, (session['user_id'], user_id, user_id, session['user_id']))
        
        messages = cursor.fetchall()
        
        # Mark messages as read
        cursor.execute("""
            UPDATE messages 
            SET is_read = TRUE 
            WHERE receiver_id = %s AND sender_id = %s AND is_read = FALSE
        """, (session['user_id'], user_id))
        
        mysql.connection.commit()
        cursor.close()
        
        return render_template('chat_conversation.html', 
                             other_user=other_user,
                             messages=messages)
        
    except Exception as e:
        print(f"Chat conversation error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error loading conversation', 'danger')
        return redirect(url_for('chat_list'))


@app.route('/chat/<int:user_id>/send', methods=['POST'])
def send_message(user_id):
    """Send a message to a user"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    message_text = request.form.get('message', '').strip()
    
    if not message_text:
        flash('Message cannot be empty', 'warning')
        return redirect(url_for('chat_conversation', user_id=user_id))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Insert message
        cursor.execute("""
            INSERT INTO messages (sender_id, receiver_id, message_text)
            VALUES (%s, %s, %s)
        """, (session['user_id'], user_id, message_text))
        
        mysql.connection.commit()
        cursor.close()
        
        return redirect(url_for('chat_conversation', user_id=user_id))
        
    except Exception as e:
        print(f"Send message error: {str(e)}")
        flash('Error sending message', 'danger')
        return redirect(url_for('chat_conversation', user_id=user_id))


@app.route('/chat/unread-count')
def get_unread_count():
    """API endpoint to get unread message count (for navbar badge)"""
    if 'user_id' not in session:
        return {'count': 0}
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM messages
            WHERE receiver_id = %s AND is_read = FALSE
        """, (session['user_id'],))
        
        result = cursor.fetchone()
        cursor.close()
        
        return {'count': result['count'] if result else 0}
        
    except Exception as e:
        print(f"Unread count error: {str(e)}")
        return {'count': 0}

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    """View detailed information about an order"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get order details
        cursor.execute("""
            SELECT o.*, 
                   c.organization_name, c.contact_person, c.contact_email, c.contact_phone,
                   c.address, c.city, c.state, c.pincode,
                   u.first_name, u.last_name
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            JOIN users u ON c.user_id = u.user_id
            WHERE o.order_id = %s
        """, (order_id,))
        
        order = cursor.fetchone()
        
        if not order:
            flash('Order not found', 'danger')
            return redirect(url_for('manage_orders'))
        
        # Check permissions
        if session.get('role') == 'client':
            cursor.execute("SELECT client_id FROM clients WHERE user_id = %s", (session['user_id'],))
            client = cursor.fetchone()
            if not client or client['client_id'] != order['client_id']:
                flash('Unauthorized access', 'danger')
                return redirect(url_for('my_orders'))
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, p.product_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        
        order_items = cursor.fetchall()
        
        # Get payment records
        cursor.execute("""
            SELECT pr.*, 
                   u.first_name as recorded_by_first, 
                   u.last_name as recorded_by_last
            FROM payment_records pr
            JOIN users u ON pr.recorded_by = u.user_id
            WHERE pr.order_id = %s
            ORDER BY pr.payment_date DESC, pr.created_at DESC
        """, (order_id,))
        
        payment_records = cursor.fetchall()
        
        cursor.close()
        
        # Get today's date for payment modal
        from datetime import date
        today = date.today().isoformat()
        
        return render_template('order_detail.html',
                             order=order,
                             order_items=order_items,
                             payment_records=payment_records,
                             today=today)
        
    except Exception as e:
        print(f"Order detail error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error loading order details', 'danger')
        return redirect(url_for('manage_orders'))

@app.route('/order/<int:order_id>/record-payment', methods=['POST'])
def record_payment(order_id):
    """Record a payment for an order"""
    if 'user_id' not in session or session.get('role') not in ['admin', 'staff']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    try:
        amount_paid = float(request.form.get('amount_paid', 0))
        payment_method = request.form.get('payment_method')
        payment_date = request.form.get('payment_date')
        reference_number = request.form.get('reference_number', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Validation
        if amount_paid <= 0:
            flash('Payment amount must be greater than zero', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        if not payment_method or payment_method not in ['bank_transfer', 'cash', 'cheque', 'upi', 'other']:
            flash('Please select a valid payment method', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        if not payment_date:
            flash('Please select payment date', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        cursor = mysql.connection.cursor()
        
        # Get order details - FIXED: Use grand_total instead of final_amount
        cursor.execute("""
            SELECT order_id, grand_total, total_paid, outstanding_amount
            FROM orders
            WHERE order_id = %s
        """, (order_id,))
        
        order = cursor.fetchone()
        
        if not order:
            flash('Order not found', 'danger')
            return redirect(url_for('manage_orders'))
        
        # Check if payment exceeds outstanding amount
        current_outstanding = float(order['outstanding_amount'] or order['grand_total'])
        if amount_paid > current_outstanding:
            flash(f'Payment amount (₹{amount_paid:.2f}) exceeds outstanding amount (₹{current_outstanding:.2f})', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        
        # Insert payment record
        cursor.execute("""
            INSERT INTO payment_records 
            (order_id, amount_paid, payment_method, payment_date, reference_number, notes, recorded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (order_id, amount_paid, payment_method, payment_date, reference_number, notes, session['user_id']))
        
        # Update order payment status - FIXED: Use grand_total
        new_total_paid = float(order['total_paid'] or 0) + amount_paid
        new_outstanding = float(order['grand_total']) - new_total_paid
        
        # Determine payment status
        if new_outstanding <= 0:
            payment_status = 'paid'
            new_outstanding = 0
        elif new_total_paid > 0:
            payment_status = 'partial'
        else:
            payment_status = 'pending'
        
        cursor.execute("""
            UPDATE orders
            SET total_paid = %s,
                outstanding_amount = %s,
                payment_status = %s
            WHERE order_id = %s
        """, (new_total_paid, new_outstanding, payment_status, order_id))
        
        mysql.connection.commit()
        cursor.close()
        
        flash(f'Payment of ₹{amount_paid:.2f} recorded successfully', 'success')
        return redirect(url_for('order_detail', order_id=order_id))
        
    except ValueError:
        flash('Invalid payment amount', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))
    except Exception as e:
        print(f"Record payment error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error recording payment', 'danger')
        return redirect(url_for('order_detail', order_id=order_id))

@app.route('/payments/test')
def payment_test():
    """Test route to verify payments routing works"""
    return f"""
    <h1>Payment Test Route Works!</h1>
    <p>User ID: {session.get('user_id')}</p>
    <p>Role: {session.get('role')}</p>
    <hr>
    <a href="{url_for('outstanding_payments')}">Try Outstanding Payments</a><br>
    <a href="{url_for('dashboard')}">Back to Dashboard</a>
    """

@app.route('/payments/outstanding')
def outstanding_payments():
    """View all orders with outstanding payments"""
    if 'user_id' not in session or session.get('role') not in ['admin', 'staff']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get all orders with outstanding payments
        cursor.execute("""
            SELECT 
                o.order_id,
                o.order_number,
                o.order_date,
                o.grand_total as final_amount,
                o.total_paid,
                o.outstanding_amount,
                o.payment_status,
                c.organization_name,
                c.contact_person,
                c.contact_email,
                c.contact_phone,
                DATEDIFF(CURDATE(), o.order_date) as days_since_order
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            WHERE o.payment_status IN ('pending', 'partial')
            ORDER BY o.order_date ASC
        """)
        
        orders = cursor.fetchall()
        
        # Calculate summary statistics
        cursor.execute("""
            SELECT 
                SUM(outstanding_amount) as total_outstanding,
                COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending_count,
                COUNT(CASE WHEN payment_status = 'partial' THEN 1 END) as partial_count,
                COUNT(CASE WHEN DATEDIFF(CURDATE(), order_date) >= 30 THEN 1 END) as overdue_count
            FROM orders
            WHERE payment_status IN ('pending', 'partial')
        """)
        
        stats = cursor.fetchone()
        
        cursor.close()
        
        return render_template('outstanding_payments.html',
                             orders=orders,
                             total_outstanding=stats['total_outstanding'] or 0,
                             pending_count=stats['pending_count'] or 0,
                             partial_count=stats['partial_count'] or 0,
                             overdue_count=stats['overdue_count'] or 0)
        
    except Exception as e:
        print(f"Outstanding payments error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error loading outstanding payments', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/payments/history')
def payment_history():
    """View all payment records"""
    if 'user_id' not in session or session.get('role') not in ['admin', 'staff']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get all payment records
        cursor.execute("""
            SELECT 
                pr.payment_id,
                pr.order_id,
                pr.amount_paid,
                pr.payment_method,
                pr.payment_date,
                pr.reference_number,
                pr.notes,
                pr.created_at,
                c.organization_name,
                c.contact_person,
                u.first_name as recorded_by_first,
                u.last_name as recorded_by_last
            FROM payment_records pr
            JOIN orders o ON pr.order_id = o.order_id
            JOIN clients c ON o.client_id = c.client_id
            JOIN users u ON pr.recorded_by = u.user_id
            ORDER BY pr.payment_date DESC, pr.created_at DESC
            LIMIT 100
        """)
        
        payment_records = cursor.fetchall()
        
        # Get payment summary
        cursor.execute("""
            SELECT 
                payment_method,
                COUNT(*) as count,
                SUM(amount_paid) as total
            FROM payment_records
            GROUP BY payment_method
        """)
        
        payment_summary = cursor.fetchall()
        
        # Get total collected
        cursor.execute("""
            SELECT 
                SUM(amount_paid) as total_collected,
                COUNT(DISTINCT order_id) as orders_with_payments
            FROM payment_records
        """)
        
        totals = cursor.fetchone()
        
        cursor.close()
        
        return render_template('payment_history.html',
                             payment_records=payment_records,
                             payment_summary=payment_summary,
                             total_collected=totals['total_collected'] or 0,
                             orders_with_payments=totals['orders_with_payments'] or 0)
        
    except Exception as e:
        print(f"Payment history error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error loading payment history', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/order/<int:order_id>/payments')
def order_payments(order_id):
    """Get payment records for a specific order (AJAX)"""
    if 'user_id' not in session:
        return {'error': 'Unauthorized'}, 401
    
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("""
            SELECT 
                pr.payment_id,
                pr.amount_paid,
                pr.payment_method,
                pr.payment_date,
                pr.reference_number,
                pr.notes,
                pr.created_at,
                u.first_name,
                u.last_name
            FROM payment_records pr
            JOIN users u ON pr.recorded_by = u.user_id
            WHERE pr.order_id = %s
            ORDER BY pr.payment_date DESC
        """, (order_id,))
        
        payments = cursor.fetchall()
        cursor.close()
        
        return {'payments': payments}
        
    except Exception as e:
        print(f"Order payments error: {str(e)}")
        return {'error': 'Failed to load payments'}, 500


@app.route('/payment/<int:payment_id>/delete', methods=['POST'])
def delete_payment(payment_id):
    """Delete a payment record (admin only)"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get payment details before deleting
        cursor.execute("""
            SELECT order_id, amount_paid
            FROM payment_records
            WHERE payment_id = %s
        """, (payment_id,))
        
        payment = cursor.fetchone()
        
        if not payment:
            flash('Payment record not found', 'danger')
            return redirect(url_for('payment_history'))
        
        order_id = payment['order_id']
        amount_paid = float(payment['amount_paid'])
        
        # Delete payment record
        cursor.execute("DELETE FROM payment_records WHERE payment_id = %s", (payment_id,))
        
        # Recalculate order payment status
        cursor.execute("""
            SELECT COALESCE(SUM(amount_paid), 0) as total_paid
            FROM payment_records
            WHERE order_id = %s
        """, (order_id,))
        
        result = cursor.fetchone()
        new_total_paid = float(result['total_paid'])
        
        # Get order final amount
        cursor.execute("SELECT final_amount FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        final_amount = float(order['final_amount'])
        
        new_outstanding = final_amount - new_total_paid
        
        # Determine payment status
        if new_outstanding <= 0:
            payment_status = 'paid'
        elif new_total_paid > 0:
            payment_status = 'partial'
        else:
            payment_status = 'pending'
        
        # Update order
        cursor.execute("""
            UPDATE orders
            SET total_paid = %s,
                outstanding_amount = %s,
                payment_status = %s
            WHERE order_id = %s
        """, (new_total_paid, new_outstanding, payment_status, order_id))
        
        mysql.connection.commit()
        cursor.close()
        
        flash('Payment record deleted successfully', 'success')
        return redirect(url_for('order_detail', order_id=order_id))
        
    except Exception as e:
        print(f"Delete payment error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error deleting payment record', 'danger')
        return redirect(url_for('payment_history'))

@app.route('/logout')
def logout():
    username = session.get('username', 'User')
    session.clear()
    session.permanent = False  # ← Add this line
    flash(f'Logged out successfully!', 'info')
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>404 - Page Not Found</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>404 - Page Not Found</h1>
        <p>The page you're looking for doesn't exist.</p>
        <a href="/">Go Home</a>
    </body>
    </html>
    ''', 404


@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors"""
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>500 - Server Error</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>500 - Server Error</h1>
        <p>Something went wrong on our end.</p>
        <a href="/">Go Home</a>
    </body>
    </html>
    ''', 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)