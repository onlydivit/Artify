from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship('Booking', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get_by_email(email):
        return User.query.filter_by(email=email).first()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'is_admin': self.is_admin,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    monument = db.Column(db.String(100), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)
    visitors = db.Column(db.JSON, nullable=True)  # Allow NULL for visitors
    qr_code = db.Column(db.Text, nullable=True)  # Allow NULL for QR code
    payment_status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50), nullable=True)  # Allow NULL for payment method
    need_guide = db.Column(db.Boolean, default=False)
    need_parking = db.Column(db.Boolean, default=False)
    base_amount = db.Column(db.Float, nullable=False, default=0.0)
    final_amount = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # New columns for additional booking details
    nationality = db.Column(db.String(20), nullable=False)  # 'indian' or 'foreigner'
    id_number = db.Column(db.String(50), nullable=False)  # Aadhar/Passport number
    camera_required = db.Column(db.Boolean, default=False)
    is_student = db.Column(db.Boolean, default=False)
    student_id = db.Column(db.String(50), nullable=True)  # Student ID number if applicable
    student_discount_applied = db.Column(db.Boolean, default=False)  # Track if student discount was applied

    def calculate_amount(self):
        """Calculate final amount including student discounts and guide fees"""
        # Base amount per person
        self.base_amount = 100.0  # Base ticket price
        
        # Guide fee if needed
        guide_fee = 500.0 if self.need_guide else 0
        
        # Calculate visitor count and student discount
        total_visitors = len(self.visitors) if self.visitors else 0
        student_count = sum(1 for v in self.visitors if v.get('is_student')) if self.visitors else 0
        regular_count = total_visitors - student_count
        
        # Apply student discount (30%)
        student_discount = 0.30
        regular_amount = regular_count * self.base_amount
        student_amount = student_count * (self.base_amount * (1 - student_discount))
        
        # Apply student discount for primary contact if applicable
        if self.is_student and self.student_id:
            student_amount += (self.base_amount * (1 - student_discount))
            self.student_discount_applied = True
        else:
            regular_amount += self.base_amount
        
        # Calculate final amount
        self.final_amount = regular_amount + student_amount + guide_fee
        return self.final_amount

    def to_dict(self):
        """Convert booking to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'monument': self.monument,
            'visit_date': self.visit_date.strftime('%Y-%m-%d'),
            'time_slot': self.time_slot,
            'visitors': self.visitors,
            'qr_code': self.qr_code,
            'payment_status': self.payment_status,
            'payment_method': self.payment_method,
            'need_guide': self.need_guide,
            'need_parking': self.need_parking,
            'base_amount': self.base_amount,
            'final_amount': self.final_amount,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'nationality': self.nationality,
            'id_number': self.id_number,
            'camera_required': self.camera_required,
            'is_student': self.is_student,
            'student_id': self.student_id,
            'student_discount_applied': self.student_discount_applied
        }

class TimeSlot(db.Model):
    __tablename__ = 'time_slots'
    
    id = db.Column(db.Integer, primary_key=True)
    monument = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, default=50)  # Maximum capacity per slot
    booked = db.Column(db.Integer, default=0)  # Number of bookings made
    
    @property
    def available(self):
        return self.capacity > self.booked

    def to_dict(self):
        return {
            'monument': self.monument,
            'date': self.date.strftime('%Y-%m-%d'),
            'time_slot': self.time_slot,
            'available_slots': self.capacity - self.booked
        }

def init_db(app):
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///artify.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    db.init_app(app)
    
    # Create all tables
    with app.app_context():
        # Drop all tables
        db.drop_all()
        # Create all tables
        db.create_all()
        print("Database tables recreated successfully!")

def register_user(name, email, password):
    """Register a new user"""
    if User.get_by_email(email):
        return False, "Email already registered"
    
    user = User(name=name, email=email)
    user.set_password(password)
    
    try:
        db.session.add(user)
        db.session.commit()
        return True, "Registration successful"
    except Exception as e:
        db.session.rollback()
        return False, f"Registration failed: {str(e)}"

def authenticate_user(email, password):
    """Authenticate a user"""
    user = User.get_by_email(email)
    if user and user.check_password(password):
        return True, user
    return False, None

def create_booking(user_id, monument, visit_date, time_slot, visitors=None, need_guide=False, need_parking=False):
    """Create a new booking"""
    try:
        # Check if time slot is available
        slot = TimeSlot.query.filter_by(
            monument=monument,
            date=visit_date,
            time_slot=time_slot
        ).first()
        
        if not slot or not slot.available:
            return False, "Selected time slot is not available"
        
        # Create the booking
        booking = Booking(
            user_id=user_id,
            monument=monument,
            visit_date=visit_date,
            time_slot=time_slot,
            visitors=visitors or [],
            need_guide=need_guide,
            need_parking=need_parking
        )
        
        # Update slot availability
        slot.booked += len(visitors or []) + 1
        
        db.session.add(booking)
        db.session.commit()
        return True, booking
        
    except Exception as e:
        db.session.rollback()
        return False, str(e)

def get_user_bookings(user_id):
    """Get all bookings for a user"""
    return Booking.query.filter_by(user_id=user_id).all()

def get_booking_by_id(booking_id):
    """Get a booking by its ID"""
    return Booking.query.get(booking_id)

def update_booking_payment(booking_id, payment_method, status='completed'):
    """Update booking payment status"""
    booking = get_booking_by_id(booking_id)
    if booking:
        booking.payment_status = status
        booking.payment_method = payment_method
        try:
            db.session.commit()
            return True, "Payment status updated"
        except Exception as e:
            db.session.rollback()
            return False, f"Update failed: {str(e)}"
    return False, "Booking not found"

def create_time_slots(monument, date):
    """Create time slots for a given monument and date"""
    slots = ['09:00-11:00', '11:00-13:00', '14:00-16:00', '16:00-18:00']
    created_slots = []
    
    for slot in slots:
        time_slot = TimeSlot(
            monument=monument,
            date=date,
            time_slot=slot
        )
        db.session.add(time_slot)
        created_slots.append(time_slot)
    
    try:
        db.session.commit()
        return True, created_slots
    except Exception as e:
        db.session.rollback()
        return False, str(e)

def get_available_slots(monument, date):
    """Get available time slots for a monument on a specific date"""
    slots = TimeSlot.query.filter_by(
        monument=monument,
        date=date
    ).all()
    
    if not slots:
        success, slots = create_time_slots(monument, date)
        if not success:
            return []
    
    return [slot.to_dict() for slot in slots if slot.available]

def update_slot_availability(monument, date, time_slot, count=1):
    """Update slot availability when a booking is made"""
    slot = TimeSlot.query.filter_by(
        monument=monument,
        date=date,
        time_slot=time_slot
    ).first()
    
    if slot and slot.available:
        slot.booked += count
        try:
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False
    return False 