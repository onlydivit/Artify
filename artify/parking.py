import os
import sys

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from auth import db, User

class ParkingSlot(db.Model):
    __tablename__ = 'parking_slots'
    
    id = db.Column(db.Integer, primary_key=True)
    monument = db.Column(db.String(100), nullable=False)
    slot_number = db.Column(db.Integer, nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False, default='4wheeler')  # 2wheeler, 4wheeler, bus
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ParkingReservation(db.Model):
    __tablename__ = 'parking_reservations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('parking_slots.id'), nullable=False)
    monument = db.Column(db.String(100), nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    driver_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    reservation_date = db.Column(db.Date, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # Duration in hours
    amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50))
    qr_code = db.Column(db.Text)  # Store QR code as base64 string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='parking_reservations')
    slot = db.relationship('ParkingSlot', backref='reservations')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'monument': self.monument,
            'vehicle_type': self.vehicle_type,
            'vehicle_number': self.vehicle_number,
            'driver_name': self.driver_name,
            'phone': self.phone,
            'reservation_date': self.reservation_date.strftime('%Y-%m-%d'),
            'duration': self.duration,
            'amount': self.amount,
            'payment_status': self.payment_status,
            'payment_method': self.payment_method,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }

def init_parking_slots():
    """Initialize exactly 30 parking slots for each monument"""
    monuments = [
        'Taj Mahal', 'Red Fort', 'Qutub Minar', 'India Gate',
        'Lotus Temple'
    ]
    
    vehicle_types = ['2wheeler', '4wheeler', 'bus']
    slots_per_type = 10  # 10 slots per vehicle type = 30 total slots
    
    try:
        # Clear existing slots
        ParkingSlot.query.delete()
        
        # Create exactly 30 slots for each monument (10 for each vehicle type)
        for monument in monuments:
            slot_number = 1
            for vehicle_type in vehicle_types:
                for _ in range(slots_per_type):
                    slot = ParkingSlot(
                        monument=monument,
                        slot_number=slot_number,
                        vehicle_type=vehicle_type,
                        is_available=True
                    )
                    db.session.add(slot)
                    slot_number += 1
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing parking slots: {str(e)}")
        return False

def get_available_slots(monument, date, vehicle_type=None):
    """Get available parking slots for a monument on a specific date"""
    query = ParkingSlot.query.filter_by(
        monument=monument,
        is_available=True
    )
    
    if vehicle_type:
        query = query.filter_by(vehicle_type=vehicle_type)
    
    # Check reservations for the date
    reserved_slots = ParkingReservation.query.filter_by(
        monument=monument,
        reservation_date=date
    ).with_entities(ParkingReservation.slot_id).all()
    
    reserved_slot_ids = [r[0] for r in reserved_slots]
    available_slots = query.filter(~ParkingSlot.id.in_(reserved_slot_ids)).all()
    
    return available_slots

def create_parking_reservation(user_id, monument, slot_id, vehicle_type, reservation_date, amount):
    """Create a new parking reservation"""
    try:
        # Check if the slot is available
        slot = ParkingSlot.query.get(slot_id)
        if not slot:
            raise Exception("Invalid parking slot")
        
        if not slot.is_available:
            raise Exception("Parking slot is not available")
        
        # Check if the slot is already reserved for the date
        existing_reservation = ParkingReservation.query.filter_by(
            slot_id=slot_id,
            reservation_date=reservation_date
        ).first()
        
        if existing_reservation:
            raise Exception("Parking slot is already reserved for this date")
        
        # Create the reservation
        reservation = ParkingReservation(
            user_id=user_id,
            monument=monument,
            slot_id=slot_id,
            vehicle_type=vehicle_type,
            reservation_date=reservation_date,
            amount=amount,
            payment_status='pending'
        )
        
        db.session.add(reservation)
        db.session.commit()
        
        return reservation
    except Exception as e:
        db.session.rollback()
        print(f"Error creating parking reservation: {str(e)}")
        raise Exception(f"Failed to create parking reservation: {str(e)}")

def update_reservation_payment(reservation_id, payment_method, status='completed'):
    """Update parking reservation payment status"""
    try:
        reservation = ParkingReservation.query.get(reservation_id)
        if not reservation:
            raise Exception("Reservation not found")
        
        reservation.payment_status = status
        reservation.payment_method = payment_method
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error updating payment status: {str(e)}")
        return False 