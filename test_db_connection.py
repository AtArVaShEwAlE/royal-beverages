"""
Database Connection Test Script - FIXED VERSION
Run this to verify MySQL connection is working
"""

from flask import Flask
from flask_mysqldb import MySQL
from config import config

# Initialize Flask app
app = Flask(__name__)

# Load configuration
app.config.from_object(config['development'])

# Initialize MySQL
mysql = MySQL(app)

def test_connection():
    """Test database connection"""
    try:
        with app.app_context():
            # Use DictCursor to get results as dictionaries
            cursor = mysql.connection.cursor()
            
            # Test query
            cursor.execute("SELECT VERSION() as version")
            version = cursor.fetchone()
            print("✅ Database connection successful!")
            print(f"MySQL Version: {version['version']}")
            
            # Count tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"\n📊 Found {len(tables)} tables in database:")
            for table in tables:
                table_name = list(table.values())[0]
                print(f"   - {table_name}")
            
            # Check admin user
            cursor.execute("SELECT username, email, role FROM users WHERE role='admin'")
            admin = cursor.fetchone()
            if admin:
                print(f"\n👤 Default Admin User:")
                print(f"   Username: {admin['username']}")
                print(f"   Email: {admin['email']}")
                print(f"   Role: {admin['role']}")
                print(f"   Password: admin123")
            else:
                print("\n⚠️ No admin user found")
            
            # Check products
            cursor.execute("SELECT COUNT(*) as count FROM products")
            product_count = cursor.fetchone()
            print(f"\n🍵 Total Products: {product_count['count']}")
            
            # Check categories
            cursor.execute("SELECT COUNT(*) as count FROM categories")
            category_count = cursor.fetchone()
            print(f"📁 Total Categories: {category_count['count']}")
            
            # Check inventory
            cursor.execute("SELECT COUNT(*) as count FROM inventory")
            inventory_count = cursor.fetchone()
            print(f"📦 Total Inventory Items: {inventory_count['count']}")
            
            cursor.close()
            
            print("\n" + "="*50)
            print("✅ ALL TESTS PASSED!")
            print("="*50)
            print("\nYour database is ready to use!")
            print("\nNext step: Run your Flask app")
            print("Command: python app.py")
            
    except Exception as e:
        print("❌ Database connection failed!")
        print(f"Error: {str(e)}")
        print(f"Error Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        print("\nPlease check:")
        print("1. MySQL is running")
        print("2. Database credentials in .env file are correct")
        print("3. Database 'royal_beverages_db' exists")

if __name__ == '__main__':
    print("Testing database connection...\n")
    test_connection()
