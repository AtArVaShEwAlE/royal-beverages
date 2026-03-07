"""
Debug script to check orders and clients in database
"""

from flask import Flask
from flask_mysqldb import MySQL
from config import config

app = Flask(__name__)
app.config.from_object(config['development'])
mysql = MySQL(app)

def debug_orders():
    """Check what's in the orders and clients tables"""
    with app.app_context():
        cursor = mysql.connection.cursor()
        
        print("\n" + "="*50)
        print("CHECKING ORDERS TABLE")
        print("="*50)
        
        # Check orders
        cursor.execute("SELECT * FROM orders")
        orders = cursor.fetchall()
        print(f"\nTotal orders in database: {len(orders)}")
        
        for order in orders:
            print(f"\nOrder ID: {order['order_id']}")
            print(f"Order Number: {order['order_number']}")
            print(f"Client ID: {order['client_id']}")
            print(f"Status: {order['status']}")
            print(f"Total: ₹{order['grand_total']}")
            print(f"Date: {order['order_date']}")
        
        print("\n" + "="*50)
        print("CHECKING CLIENTS TABLE")
        print("="*50)
        
        # Check clients
        cursor.execute("SELECT * FROM clients")
        clients = cursor.fetchall()
        print(f"\nTotal clients in database: {len(clients)}")
        
        for client in clients:
            print(f"\nClient ID: {client['client_id']}")
            print(f"User ID: {client['user_id']}")
            print(f"Organization: {client['organization_name']}")
            print(f"Contact Person: {client['contact_person']}")
        
        print("\n" + "="*50)
        print("CHECKING USERS TABLE")
        print("="*50)
        
        # Check users with role client
        cursor.execute("SELECT * FROM users WHERE role = 'client'")
        users = cursor.fetchall()
        print(f"\nTotal client users in database: {len(users)}")
        
        for user in users:
            print(f"\nUser ID: {user['user_id']}")
            print(f"Username: {user['username']}")
            print(f"Email: {user['email']}")
            print(f"Name: {user['first_name']} {user['last_name']}")
        
        print("\n" + "="*50)
        print("CHECKING ORDER ITEMS")
        print("="*50)
        
        # Check order items
        cursor.execute("""
            SELECT oi.*, p.product_name 
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
        """)
        items = cursor.fetchall()
        print(f"\nTotal order items: {len(items)}")
        
        for item in items:
            print(f"\nOrder ID: {item['order_id']}")
            print(f"Product: {item['product_name']}")
            print(f"Quantity: {item['quantity']}")
            print(f"Price: ₹{item['total_price']}")
        
        cursor.close()
        
        print("\n" + "="*50)
        print("DEBUG COMPLETE")
        print("="*50 + "\n")

if __name__ == '__main__':
    debug_orders()
