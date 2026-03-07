"""
Test script to check if manage_orders query works
"""

from flask import Flask
from flask_mysqldb import MySQL
from config import config

app = Flask(__name__)
app.config.from_object(config['development'])
mysql = MySQL(app)

def test_manage_orders_query():
    """Test the exact query used in manage_orders route"""
    with app.app_context():
        cursor = mysql.connection.cursor()
        
        print("\n" + "="*50)
        print("TESTING MANAGE ORDERS QUERY")
        print("="*50)
        
        # Exact query from manage_orders route
        cursor.execute("""
            SELECT o.*, 
                   c.organization_name, c.contact_person, c.contact_email, c.contact_phone
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            ORDER BY o.order_date DESC
        """)
        orders = cursor.fetchall()
        
        print(f"\nQuery returned {len(orders)} orders")
        
        if len(orders) > 0:
            print("\n✅ Query is working! Orders found:")
            for order in orders:
                print(f"\nOrder Number: {order['order_number']}")
                print(f"Client: {order['organization_name']}")
                print(f"Status: {order['status']}")
                print(f"Total: ₹{order['grand_total']}")
                
                # Get order items
                cursor.execute("""
                    SELECT oi.*, p.product_name
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.product_id
                    WHERE oi.order_id = %s
                """, (order['order_id'],))
                items = cursor.fetchall()
                
                print(f"Items count: {len(items)}")
                for item in items:
                    print(f"  - {item['product_name']}: {item['quantity']} x ₹{item['unit_price']}")
        else:
            print("\n❌ Query returned 0 orders - there's a problem!")
        
        cursor.close()
        
        print("\n" + "="*50)
        print("TEST COMPLETE")
        print("="*50 + "\n")

if __name__ == '__main__':
    test_manage_orders_query()
