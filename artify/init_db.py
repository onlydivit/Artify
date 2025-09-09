import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

# Create Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///artify.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy()
db.init_app(app)

# Import models after db initialization to avoid circular imports
from auth import User
from parking import ParkingSlot

def init_directories():
    """Initialize required directories"""
    # Create static directory if it doesn't exist
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    
    # Create QR codes directory
    qr_codes_dir = os.path.join(static_dir, 'qr_codes')
    if not os.path.exists(qr_codes_dir):
        os.makedirs(qr_codes_dir)

def create_admin_user():
    """Create an admin user"""
    admin = User(
        name='Admin',
        email='admin@artify.com',
        is_admin=True
    )
    admin.set_password('admin123')  # Change this password in production
    db.session.add(admin)
    db.session.commit()

def init_database():
    print("Starting database initialization...")
    
    # Initialize directories
    print("Creating required directories...")
    init_directories()
    
    # Drop and recreate all tables
    print("Dropping and recreating tables...")
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Create admin user
        print("Creating admin user...")
        create_admin_user()
        
        print("Database initialized!")

if __name__ == "__main__":
    with app.app_context():
        init_database() 