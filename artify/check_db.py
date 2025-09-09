from app import app
from auth import db, Booking

with app.app_context():
    # Print all tables
    print("Tables in database:")
    for table in db.metadata.tables:
        print(f"- {table}")
    
    # Print Booking table columns
    print("\nBooking table columns:")
    for column in Booking.__table__.columns:
        print(f"- {column.name} ({column.type})") 