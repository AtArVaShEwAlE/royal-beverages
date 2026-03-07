# 🍵 Royal Beverages - Supply & Distribution Management System

A comprehensive Flask-based web application for managing beverage supply and distribution operations.

## 📋 Features

### Admin Features
- **Dashboard** - Overview of business metrics and recent activities
- **Product Management** - Add, edit, activate/deactivate products
- **Order Management** - Approve, pack, dispatch orders with stock deduction
- **Inventory Management** - Track stock levels, add/remove stock, view history
- **Delivery Management** - Assign delivery personnel, track deliveries
- **Client Management** - View all registered clients
- **Reports & Analytics** - Sales reports, top products, charts
- **Invoice Generation** - Automated PDF invoices with GST

### Client Features
- **Client Dashboard** - Order statistics and recent orders
- **Place Order** - Browse products and create orders
- **My Orders** - View order history, track status, download invoices
- **Feedback System** - Rate and review delivered orders
- **Profile Management** - Update business and personal information

## 🛠️ Technology Stack

- **Backend:** Flask (Python)
- **Database:** MySQL
- **PDF Generation:** ReportLab
- **Frontend:** HTML5, CSS3, JavaScript
- **Authentication:** Session-based with password hashing (Werkzeug)

## 📦 Installation

### Prerequisites
- Python 3.8+
- MySQL Server
- pip (Python package manager)

### Step 1: Clone Repository
```bash
git clone https://github.com/yourusername/royal-beverages.git
cd royal-beverages
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Database Setup
1. Create MySQL database:
```sql
CREATE DATABASE royal_beverages_db;
```

2. Import schema (if provided):
```bash
mysql -u root -p royal_beverages_db < database_schema.sql
```

3. Update database configuration in `app.py`:
```python
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'your_username'
app.config['MYSQL_PASSWORD'] = 'your_password'
app.config['MYSQL_DB'] = 'royal_beverages_db'
```

### Step 5: Run Application
```bash
python app.py
```

Visit: `http://localhost:5000`

## 🔐 Default Credentials

**Admin Login:**
- Username: `admin`
- Password: `Admin@2024`

**Note:** Change default password after first login!

## 📁 Project Structure

```
royal_beverages/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── static/
│   ├── css/
│   │   ├── style.css     # Main stylesheet
│   │   └── products.css  # Product-specific styles
│   ├── js/
│   │   └── main.js       # JavaScript functions
│   └── images/
│       └── RBLOGO.svg    # Company logo
└── templates/
    ├── base.html         # Base template
    ├── login.html        # Login page
    ├── signup.html       # Registration page
    ├── dashboard.html    # Admin dashboard
    ├── client_dashboard.html
    ├── products.html
    ├── manage_orders.html
    ├── inventory.html
    ├── delivery.html
    ├── clients.html
    ├── reports.html
    ├── profile.html
    ├── place_order.html
    └── my_orders.html
```

## 🔧 Configuration

### Environment Variables (Recommended)
Create a `.env` file:
```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DB=royal_beverages_db
```

### Security Notes
- Never commit `.env` file to Git
- Change default SECRET_KEY in production
- Use strong passwords for database
- Enable HTTPS in production

## 📊 Database Schema

### Core Tables
- `users` - User authentication and profiles
- `clients` - Client business information
- `categories` - Product categories
- `products` - Product catalog
- `orders` - Order records
- `order_items` - Order line items
- `stock_logs` - Inventory transaction history
- `feedback` - Order feedback and ratings

## 🚀 Deployment

### Production Checklist
- [ ] Set `DEBUG = False` in app.py
- [ ] Use production-grade WSGI server (Gunicorn/uWSGI)
- [ ] Configure reverse proxy (Nginx/Apache)
- [ ] Enable HTTPS/SSL
- [ ] Set secure SECRET_KEY
- [ ] Configure database backups
- [ ] Set up logging
- [ ] Enable rate limiting
- [ ] Review security headers

### Example: Deploy with Gunicorn + Nginx

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

3. Configure Nginx reverse proxy
4. Set up systemd service for auto-start

## 🧪 Testing

Run the application and test:
1. ✅ Admin login
2. ✅ Client registration
3. ✅ Place order workflow
4. ✅ Order approval → stock deduction
5. ✅ Invoice generation
6. ✅ Delivery tracking
7. ✅ Reports generation

## 📝 Password Requirements

All new signups require:
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character (!@#$%^&*)

## 🏢 Company Information

**Royal Beverages Supply & Distribution**
- GSTIN: 27CUZPS1971H1ZP
- Email: support@royalbeverages.com

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/NewFeature`)
3. Commit changes (`git commit -m 'Add NewFeature'`)
4. Push to branch (`git push origin feature/NewFeature`)
5. Open Pull Request

## 📄 License

This project is proprietary software. All rights reserved.

## 👨‍💻 Developer

Developed for Royal Beverages Supply & Distribution

## 📞 Support

For technical support, contact: dev@royalbeverages.com

## 🔄 Version History

### v1.0.0 (2024-03-07)
- Initial release
- Complete order management system
- Invoice generation with GST
- Inventory tracking
- Feedback system
- Reports and analytics

---

**Built with ❤️ using Flask**
