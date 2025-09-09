import os
import sys

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from functools import wraps
import qrcode
import io
import base64
from datetime import datetime
from io import BytesIO
import socket
import json
import uuid
import tempfile

# Import local modules
from auth import (
    db, init_db, User, Booking, TimeSlot,
    register_user, authenticate_user, create_booking,
    get_booking_by_id, update_booking_payment,
    get_available_slots as get_booking_slots,
    update_slot_availability
)
from parking import (
    ParkingSlot,
    ParkingReservation,
    init_parking_slots,
    get_available_slots as get_parking_slots,
    create_parking_reservation,
    update_reservation_payment
)

# Optional imports for speech recognition
try:
    import speech_recognition as sr
    from gtts import gTTS
    SPEECH_ENABLED = True
except ImportError:
    SPEECH_ENABLED = False
    print("Speech recognition features will be disabled")

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate a secure random secret key

# Set the instance path
app.instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

# Create directory for QR codes if it doesn't exist
qr_code_dir = os.path.join(app.static_folder, 'qr_codes')
if not os.path.exists(qr_code_dir):
    os.makedirs(qr_code_dir)

# Initialize database
init_db(app)

def init_app():
    # Initialize parking slots when the app starts
    with app.app_context():
        init_parking_slots()

# Initialize the app
init_app()

# Add this dictionary with monument data
MONUMENTS_DATA = {
    'Red Fort': {
        'name': 'Red Fort (Lal Qila)',
        'short_description': 'A historic fort built by Mughal Emperor Shah Jahan',
        'image_url': 'https://source.unsplash.com/1600x900/?red-fort-delhi',
        'history': '''The Red Fort, also known as Lal Qila, was built by Mughal Emperor Shah Jahan in 1639. 
        It served as the main residence of the Mughal emperors for nearly 200 years. The fort's construction 
        began in 1638 and was completed in 1648. The name "Red Fort" comes from its massive red sandstone walls. 
        The fort was designed by architect Ustad Ahmad Lahori, who also designed the Taj Mahal.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'The fort showcases a perfect blend of Persian, Timurid, and Hindu architectural styles.'
            },
            {
                'title': 'Diwan-i-Aam',
                'description': 'The Hall of Public Audience where the emperor would meet the general public.'
            },
            {
                'title': 'Diwan-i-Khas',
                'description': 'The Hall of Private Audience where the emperor would meet important guests.'
            }
        ],
        'timing': '9:30 AM - 4:30 PM (Closed on Mondays)',
        'entry_fee': '₹25 for Indians, ₹50 for Foreigners',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.6562!2d77.2410!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2410!3d28.6562!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sRed%20Fort!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Red+Fort+Delhi'
    },
    'Qutub Minar': {
        'name': 'Qutub Minar',
        'short_description': 'The tallest brick minaret in the world',
        'image_url': 'https://source.unsplash.com/1600x900/?qutub-minar',
        'history': '''Qutub Minar was built in 1192 by Qutub-ud-din Aibak, the founder of the Delhi Sultanate. 
        The construction was completed by his successor Iltutmish. The minaret is 73 meters tall and has 379 steps. 
        It is made of red sandstone and marble, with intricate carvings and verses from the Quran.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A masterpiece of Indo-Islamic architecture with five distinct storeys.'
            },
            {
                'title': 'Iron Pillar',
                'description': 'A 7-meter tall iron pillar that has not rusted for over 1600 years.'
            },
            {
                'title': 'Quwwat-ul-Islam Mosque',
                'description': 'The first mosque built in India, located at the base of the minaret.'
            }
        ],
        'timing': '7:00 AM - 5:00 PM (Open all days)',
        'entry_fee': '₹30 for Indians, ₹60 for Foreigners',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.5244!2d77.1855!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.1855!3d28.5244!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sQutub%20Minar!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Qutub+Minar+Delhi'
    },
    'India Gate': {
        'name': 'India Gate',
        'short_description': 'A war memorial dedicated to Indian soldiers',
        'image_url': 'https://source.unsplash.com/1600x900/?india-gate',
        'history': '''India Gate was built in 1931 to commemorate the 70,000 Indian soldiers who died in World War I. 
        The monument was designed by Edwin Lutyens and is inspired by the Arc de Triomphe in Paris. 
        The names of 13,300 servicemen are inscribed on the walls.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A 42-meter tall archway made of red and pale sandstone and granite.'
            },
            {
                'title': 'Amar Jawan Jyoti',
                'description': 'An eternal flame burning in memory of soldiers who died in the 1971 Indo-Pakistan War.'
            },
            {
                'title': 'Surrounding Gardens',
                'description': 'Beautiful lawns and gardens perfect for evening walks and picnics.'
            }
        ],
        'timing': 'Open 24 hours',
        'entry_fee': 'Free for all visitors',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.6129!2d77.2295!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2295!3d28.6129!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sIndia%20Gate!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=India+Gate+Delhi'
    },
    'Taj Mahal': {
        'name': 'Taj Mahal',
        'short_description': 'One of the Seven Wonders of the World',
        'image_url': 'https://source.unsplash.com/1600x900/?taj-mahal',
        'history': '''The Taj Mahal was commissioned in 1632 by Mughal Emperor Shah Jahan to house the tomb of his 
        favorite wife, Mumtaz Mahal. Construction was completed in 1653. The monument is considered the finest 
        example of Mughal architecture, combining Persian, Ottoman Turkish, and Indian architectural styles.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A perfect blend of Persian, Ottoman Turkish, and Indian architectural styles.'
            },
            {
                'title': 'Main Mausoleum',
                'description': 'The central structure housing the tombs of Shah Jahan and Mumtaz Mahal.'
            },
            {
                'title': 'Gardens',
                'description': 'Beautiful Mughal gardens with reflecting pools and fountains.'
            }
        ],
        'timing': 'Sunrise to Sunset (Closed on Fridays)',
        'entry_fee': '₹40 for Indians, ₹80 for Foreigners',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d27.1751!2d78.0421!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d78.0421!3d27.1751!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x39747121d702ff6d%3A0xdd2ae4807feb8530!2sTaj%20Mahal!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Taj+Mahal+Agra'
    },
    'Lotus Temple': {
        'name': 'Lotus Temple',
        'short_description': 'A Bahá\'í House of Worship',
        'image_url': 'https://source.unsplash.com/1600x900/?lotus-temple',
        'history': '''The Lotus Temple, completed in 1986, is a Bahá\'í House of Worship. It was designed by 
        Iranian architect Fariborz Sahba and is notable for its flowerlike shape. The temple has won numerous 
        architectural awards and is one of the most visited buildings in the world.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A unique lotus-shaped structure with 27 free-standing marble-clad "petals".'
            },
            {
                'title': 'Interior',
                'description': 'A central hall with a capacity of 2,500 people and excellent acoustics.'
            },
            {
                'title': 'Gardens',
                'description': 'Beautiful landscaped gardens with nine pools and walkways.'
            }
        ],
        'timing': '9:00 AM - 5:30 PM (Closed on Mondays)',
        'entry_fee': 'Free for all visitors',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.5535!2d77.2588!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2588!3d28.5535!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sLotus%20Temple!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Lotus+Temple+Delhi'
    },
    'Jama Masjid': {
        'name': 'Jama Masjid',
        'short_description': 'One of the largest mosques in India',
        'image_url': 'https://source.unsplash.com/1600x900/?jama-masjid',
        'history': '''Jama Masjid was built by Mughal Emperor Shah Jahan between 1650 and 1656. The mosque 
        was inaugurated by Syed Abdul Ghafoor Shah Bukhari, a religious leader from Uzbekistan. It is the 
        largest mosque in India and can accommodate 25,000 worshippers.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A magnificent example of Mughal architecture with three domes and two minarets.'
            },
            {
                'title': 'Courtyard',
                'description': 'A vast courtyard that can hold thousands of worshippers.'
            },
            {
                'title': 'Relics',
                'description': 'Houses several relics of Islamic religious significance.'
            }
        ],
        'timing': '7:00 AM - 12:00 PM, 1:30 PM - 6:30 PM (Closed during prayer times)',
        'entry_fee': 'Free for Indian visitors, ₹35 for Foreign visitors',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.6507!2d77.2334!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2334!3d28.6507!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sJama%20Masjid!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Jama+Masjid+Delhi'
    },
    'Purana Qila': {
        'name': 'Purana Qila (Old Fort)',
        'short_description': 'The oldest fort in Delhi',
        'image_url': 'https://source.unsplash.com/1600x900/?purana-qila',
        'history': '''Purana Qila, also known as Old Fort, is believed to be the site of Indraprastha, 
        the ancient city of the Mahabharata. The current structure was built by Sher Shah Suri in 1538. 
        The fort has witnessed the rise and fall of several empires.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A blend of Afghan and Mughal architectural styles.'
            },
            {
                'title': 'Qila-i-Kuhna Mosque',
                'description': 'A beautiful mosque built by Sher Shah Suri.'
            },
            {
                'title': 'Sher Mandal',
                'description': 'An octagonal tower believed to be Humayun\'s library.'
            }
        ],
        'timing': '7:00 AM - 5:00 PM (Open all days)',
        'entry_fee': '₹20 for Indians, ₹40 for Foreigners',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.6092!2d77.2439!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2439!3d28.6092!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sPurana%20Qila!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Purana+Qila+Delhi'
    },
    'National War Memorial': {
        'name': 'National War Memorial',
        'short_description': 'A tribute to Indian soldiers',
        'image_url': 'https://source.unsplash.com/1600x900/?national-war-memorial',
        'history': '''The National War Memorial was inaugurated in 2019 to honor the soldiers who have 
        served in the armed forces since India\'s independence. The memorial commemorates the sacrifices 
        of over 25,942 soldiers who have laid down their lives for the nation.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A modern architectural marvel with four concentric circles.'
            },
            {
                'title': 'Amar Chakra',
                'description': 'The innermost circle with the eternal flame.'
            },
            {
                'title': 'Veerta Chakra',
                'description': 'Gallantry award winners\' names inscribed on walls.'
            }
        ],
        'timing': '9:00 AM - 7:30 PM (Open all days)',
        'entry_fee': 'Free for all visitors',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.youtube.com/embed/dQw4w9WgXcQ'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2295!3d28.6129!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sNational%20War%20Memorial!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=National+War+Memorial+Delhi'
    },
    'Rashtrapati Bhavan': {
        'name': 'Rashtrapati Bhavan',
        'short_description': 'The official residence of the President of India',
        'image_url': 'https://source.unsplash.com/1600x900/?rashtrapati-bhavan',
        'history': '''Rashtrapati Bhavan was designed by British architects Edwin Lutyens and Herbert Baker. 
        Construction began in 1912 and was completed in 1929. It was originally built as the Viceroy\'s House 
        during British rule and became the President\'s residence after India\'s independence.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A blend of Indian and Western architectural styles with 340 rooms.'
            },
            {
                'title': 'Mughal Gardens',
                'description': 'Beautiful gardens spread over 15 acres with rare flowers and plants.'
            },
            {
                'title': 'Darbar Hall',
                'description': 'The grand ceremonial hall used for official functions.'
            }
        ],
        'timing': '9:00 AM - 4:00 PM (Closed on Mondays)',
        'entry_fee': '₹15 for Indians, ₹30 for Foreigners',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.6143!2d77.1990!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.1990!3d28.6143!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sRashtrapati%20Bhavan!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Rashtrapati+Bhavan+Delhi'
    },
    'Raj Ghat': {
        'name': 'Raj Ghat',
        'short_description': 'Memorial to Mahatma Gandhi',
        'image_url': 'https://source.unsplash.com/1600x900/?raj-ghat',
        'history': '''Raj Ghat is a memorial dedicated to Mahatma Gandhi, marking the spot of his cremation 
        on January 31, 1948. The memorial is a simple black marble platform with an eternal flame burning 
        at one end. The memorial is surrounded by beautiful gardens.''',
        'highlights': [
            {
                'title': 'Memorial Platform',
                'description': 'A simple black marble platform marking the spot of Gandhi\'s cremation.'
            },
            {
                'title': 'Eternal Flame',
                'description': 'A flame that burns continuously in memory of the Father of the Nation.'
            },
            {
                'title': 'Gardens',
                'description': 'Beautiful gardens with trees planted by various world leaders.'
            }
        ],
        'timing': '6:30 AM - 6:00 PM (Open all days)',
        'entry_fee': 'Free for all visitors',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.youtube.com/embed/JSwo2f2xFNQ'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2489!3d28.6415!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sRaj%20Ghat!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Raj+Ghat+Delhi'
    },
    'Jantar Mantar': {
        'name': 'Jantar Mantar',
        'short_description': 'An astronomical observatory',
        'image_url': 'https://source.unsplash.com/1600x900/?jantar-mantar',
        'history': '''Jantar Mantar was built by Maharaja Jai Singh II of Jaipur in 1724. It is one of five 
        astronomical observatories built by him across India. The observatory was used to compile astronomical 
        tables and predict the times and movements of the sun, moon, and planets.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A collection of 13 architectural astronomy instruments.'
            },
            {
                'title': 'Samrat Yantra',
                'description': 'The world\'s largest sundial, accurate to within 20 seconds.'
            },
            {
                'title': 'Rama Yantra',
                'description': 'Used to measure the altitude and azimuth of celestial objects.'
            }
        ],
        'timing': '9:00 AM - 4:30 PM (Open all days)',
        'entry_fee': '₹20 for Indians, ₹40 for Foreigners',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.6277!2d77.2167!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2167!3d28.6277!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sJantar%20Mantar!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Jantar+Mantar+Delhi'
    },
    'Akshardham Temple': {
        'name': 'Akshardham Temple',
        'short_description': 'A modern Hindu temple complex',
        'image_url': 'https://source.unsplash.com/1600x900/?akshardham-temple',
        'history': '''Akshardham Temple was inaugurated in 2005 by Pramukh Swami Maharaj. The temple complex 
        showcases traditional Hindu and Indian culture, spirituality, and architecture. It was built using 
        ancient architectural principles and modern technology.''',
        'highlights': [
            {
                'title': 'Architecture',
                'description': 'A stunning example of traditional Hindu architecture with intricate carvings.'
            },
            {
                'title': 'Exhibitions',
                'description': 'Interactive exhibitions showcasing Indian culture and spirituality.'
            },
            {
                'title': 'Musical Fountain',
                'description': 'A spectacular water show in the evening.'
            }
        ],
        'timing': '9:30 AM - 6:30 PM (Closed on Mondays)',
        'entry_fee': '₹15 for Indians, ₹30 for Foreigners',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.youtube.com/embed/DwsYVv36Vo0'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2777!3d28.6129!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sAkshardham%20Temple!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Akshardham+Temple+Delhi'
    },
    'Lodi Gardens': {
        'name': 'Lodi Gardens',
        'short_description': 'A city park with historical monuments',
        'image_url': 'https://source.unsplash.com/1600x900/?lodi-gardens',
        'history': '''Lodi Gardens was built in 1936 by the British to preserve the tombs of the Sayyid and 
        Lodi dynasties. The park was designed by Lady Willingdon, the wife of the Viceroy of India. It is 
        now a popular recreational spot in Delhi.''',
        'highlights': [
            {
                'title': 'Tombs',
                'description': 'Several historical tombs from the Sayyid and Lodi periods.'
            },
            {
                'title': 'Gardens',
                'description': 'Beautiful landscaped gardens with rare trees and plants.'
            },
            {
                'title': 'Architecture',
                'description': 'Fine examples of Indo-Islamic architecture.'
            }
        ],
        'timing': '6:00 AM - 8:00 PM (Open all days)',
        'entry_fee': 'Free for all visitors',
        'best_time': 'October to March (Winter Season)',
        'virtual_tour_urls': [
            'https://www.google.com/maps/embed?pb=!4v1648123456789!6m8!1m7!1sCAESLEdpbGxlcm9lR0FTRS1ldXdJR1JfYl9nS2dCbGdCbGdCbGdCbGdCbGdCbGc!2m2!1d28.5933!2d77.2197!3f0!4f0!5f0.7820865974627469'
        ],
        'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3500.8389774351086!2d77.2197!3d28.5933!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x390cfd5b347f62e7%3A0x37205b715389640!2sLodi%20Gardens!5e0!3m2!1sen!2sin!4v1648123456789!5m2!1sen!2sin',
        'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=Lodi+Gardens+Delhi'
    }
}

@app.route('/')
def index():
    return redirect(url_for('auth'))

@app.route('/auth')
def auth():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('auth.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    # Add validations
    if not email or not password:
        flash('Please fill in all fields')
        return redirect(url_for('auth'))
    
    if not '@' in email or not '.' in email:
        flash('Please enter a valid email address')
        return redirect(url_for('auth'))
    
    if len(password) < 6:
        flash('Password must be at least 6 characters long')
        return redirect(url_for('auth'))
    
    success, user = authenticate_user(email, password)
    if success:
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        return redirect(url_for('home'))
    else:
        flash('Invalid email or password')
        return redirect(url_for('auth'))

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate email format
    if not email or not '@' in email or not '.' in email:
        flash('Please enter a valid email address with @ and . characters')
        return redirect(url_for('auth'))
    
    # Validate password length and format
    if not password or len(password) < 8:
        flash('Password must be at least 8 characters long')
        return redirect(url_for('auth'))
    
    if password != confirm_password:
        flash('Passwords do not match')
        return redirect(url_for('auth'))
    
    success, message = register_user(name, email, password)
    flash(message)
    return redirect(url_for('auth'))

@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('auth'))

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    return render_template('home.html', user_name=session.get('user_name'))

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'user_id' not in session:
        flash('Please login to make a booking')
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        monument = request.form.get('monument')
        visit_date = request.form.get('date')
        name = request.form.get('name')
        age = request.form.get('age')
        email = request.form.get('email')
        time_slot = request.form.get('time_slot')
        num_visitors = request.form.get('visitors')
        
        # Add validations
        if not all([monument, visit_date, name, age, email, time_slot]):
            flash('Please fill in all required fields')
            return redirect(url_for('booking'))
        
        # Validate email
        if not '@' in email or not '.' in email:
            flash('Please enter a valid email address')
            return redirect(url_for('booking'))
        
        # Validate age
        try:
            age = int(age)
            if age < 0 or age > 120:
                flash('Please enter a valid age')
                return redirect(url_for('booking'))
        except ValueError:
            flash('Age must be a number')
            return redirect(url_for('booking'))
        
        # Validate date
        try:
            visit_date_obj = datetime.strptime(visit_date, '%Y-%m-%d')
            if visit_date_obj.date() < datetime.now().date():
                flash('Please select a future date')
                return redirect(url_for('booking'))
        except ValueError:
            flash('Invalid date format')
            return redirect(url_for('booking'))
        
        # Validate number of visitors
        try:
            num_visitors = int(num_visitors) if num_visitors else 0
            if num_visitors < 0 or num_visitors > 10:
                flash('Number of visitors must be between 0 and 10')
                return redirect(url_for('booking'))
        except ValueError:
            flash('Number of visitors must be a number')
            return redirect(url_for('booking'))
        
        # Validate visitor details if any
        if num_visitors > 0:
            for i in range(num_visitors):
                visitor_name = request.form.get(f'visitor_name_{i}')
                visitor_age = request.form.get(f'visitor_age_{i}')
                
                if not visitor_name or not visitor_age:
                    flash('Please fill in all visitor details')
                    return redirect(url_for('booking'))
                
                try:
                    visitor_age = int(visitor_age)
                    if visitor_age < 0 or visitor_age > 120:
                        flash('Please enter valid age for all visitors')
                        return redirect(url_for('booking'))
                except ValueError:
                    flash('Visitor age must be a number')
                    return redirect(url_for('booking'))
        
        # Get monument entry fee from MONUMENTS_DATA
        monument_data = MONUMENTS_DATA.get(monument, {})
        entry_fee_str = monument_data.get('entry_fee', '₹0 for Indians, ₹0 for Foreigners')
        
        # Parse entry fee for Indians (assuming format "₹X for Indians, ₹Y for Foreigners")
        try:
            indian_fee = int(entry_fee_str.split('for Indians')[0].replace('₹', '').strip())
        except:
            indian_fee = 0
        
        # Store booking details in session for payment
        session['booking_details'] = {
            'monument': monument,
            'date': visit_date,
            'name': name,
            'age': age,
            'email': email,
            'time_slot': time_slot,
            'num_visitors': num_visitors,
            'user_id': session['user_id'],
            'entry_fee': indian_fee
        }
        
        return redirect(url_for('payment'))
    
    return render_template('booking.html', monuments_data=MONUMENTS_DATA)

@app.route('/get_available_slots')
def available_slots():
    monument = request.args.get('monument')
    date_str = request.args.get('date')
    
    if not monument or not date_str:
        return jsonify([])
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        slots = get_booking_slots(monument, date)
        return jsonify(slots)
    except ValueError:
        return jsonify([])

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        # Get form data with default values
        name = request.form.get('name', '')
        age = request.form.get('age', '0')
        email = request.form.get('email', '')
        monument = request.form.get('monument', '')
        visit_date = request.form.get('date', '')
        time_slot = request.form.get('time_slot', '')
        is_student = request.form.get('is_student') == 'on'
        num_visitors = int(request.form.get('visitors', '0'))
        need_guide = request.form.get('need_guide') == 'on'
        
        # Get monument entry fee from MONUMENTS_DATA
        monument_data = MONUMENTS_DATA.get(monument, {})
        entry_fee_str = monument_data.get('entry_fee', '₹0 for Indians, ₹0 for Foreigners')
        
        # Parse entry fee for Indians
        try:
            base_amount = int(entry_fee_str.split('for Indians')[0].replace('₹', '').strip())
        except:
            base_amount = 0
        
        total_visitors = num_visitors + 1  # +1 for the primary visitor
        guide_fee = 300 if need_guide else 0
        
        # Calculate base amount with entry fees
        final_amount = (base_amount * total_visitors) + guide_fee
        
        # Apply student discount if applicable
        if is_student:
            final_amount -= (base_amount * 0.3)  # 30% discount for primary contact
        
        booking_data = {
            'monument': monument,
            'date': visit_date,
            'name': name,
            'email': email,
            'age': int(age),
            'time_slot': time_slot,
            'is_student': is_student,
            'need_guide': need_guide,
            'base_amount': base_amount,
            'guide_fee': guide_fee,
            'final_amount': final_amount
        }
        
        return render_template('payment.html', booking=booking_data)
    
    if 'booking_details' not in session:
        return redirect(url_for('booking'))
    
    booking_details = session['booking_details']
    user = User.query.get(session['user_id'])
    
    # Get monument entry fee from MONUMENTS_DATA
    monument_data = MONUMENTS_DATA.get(booking_details['monument'], {})
    entry_fee_str = monument_data.get('entry_fee', '₹0 for Indians, ₹0 for Foreigners')
    
    # Parse entry fee for Indians
    try:
        base_amount = int(entry_fee_str.split('for Indians')[0].replace('₹', '').strip())
    except:
        base_amount = 0
    
    total_visitors = booking_details.get('num_visitors', 0) + 1  # +1 for the primary visitor
    guide_fee = 300 if booking_details.get('need_guide', False) else 0
    
    # Calculate base amount with entry fees
    final_amount = (base_amount * total_visitors) + guide_fee
    
    # Apply student discount if applicable
    if booking_details.get('is_student', False):
        final_amount -= (base_amount * 0.3)  # 30% discount for primary contact
    
    booking_data = {
        'monument': booking_details['monument'],
        'date': booking_details['date'],
        'name': user.name,
        'email': user.email,
        'age': booking_details.get('age', 0),
        'time_slot': booking_details.get('time_slot', ''),
        'is_student': booking_details.get('is_student', False),
        'need_guide': booking_details.get('need_guide', False),
        'base_amount': base_amount,
        'guide_fee': guide_fee,
        'final_amount': final_amount
    }
    
    return render_template('payment.html', booking=booking_data)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'error': 'Please login to continue'
        })

    try:
        # Get payment data from request
        payment_data = request.get_json()
        if not payment_data:
            return jsonify({
                'success': False,
                'error': 'Invalid payment data'
            })

        # Get required fields
        payment_method = payment_data.get('payment_method')
        booking_data = payment_data.get('booking_data')
        time_slot = payment_data.get('time_slot')
        id_number = payment_data.get('id_number')
        camera_required = payment_data.get('camera_required') == 'true'
        is_student = payment_data.get('is_student') == 'true'

        # Validate required fields
        required_fields = {
            'payment_method': payment_method,
            'booking_data': booking_data,
            'time_slot': time_slot,
            'id_number': id_number
        }

        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            })

        # Validate payment method specific fields
        if payment_method == 'card':
            if not all(payment_data.get(field) for field in ['card_number', 'expiry', 'cvv', 'card_name']):
                return jsonify({
                    'success': False,
                    'error': 'Missing required card payment information'
                })
        elif payment_method == 'upi':
            if not payment_data.get('upi_id'):
                return jsonify({
                    'success': False,
                    'error': 'Missing UPI ID'
                })
        elif payment_method == 'netbanking':
            if not payment_data.get('bank'):
                return jsonify({
                    'success': False,
                    'error': 'Missing bank selection'
                })

        # Get the user from the database
        user = User.query.get(session['user_id'])
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            })

        try:
            visit_date = datetime.strptime(booking_data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format'
            })

        # Create booking record
        booking = Booking(
            user_id=user.id,
            monument=booking_data['monument'],
            visit_date=visit_date,
            time_slot=time_slot,
            visitors=json.dumps(booking_data.get('visitors', [])),
            need_guide=booking_data.get('need_guide', False),
            need_parking=booking_data.get('need_parking', False),
            base_amount=float(booking_data.get('base_amount', 0)),
            final_amount=float(booking_data.get('final_amount', 0)),
            payment_status='completed',
            payment_method=payment_method,
            id_number=id_number,
            camera_required=camera_required,
            is_student=is_student,
            student_discount_applied=booking_data.get('student_discount_applied', False),
            nationality='Indian'  # Set default nationality
        )

        # Add booking to database
        db.session.add(booking)
        db.session.commit()

        # Generate QR code
        qr_data = {
            'booking_id': booking.id,
            'monument': booking_data['monument'],
            'date': booking_data['date'],
            'time_slot': time_slot,
            'name': user.name,
            'email': user.email,
            'visitors': booking_data.get('visitors', []),
            'is_student': is_student,
            'need_guide': booking_data.get('need_guide', False),
            'need_parking': booking_data.get('need_parking', False),
            'id_number': id_number,
            'camera_required': camera_required
        }

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Convert QR code to base64
        buffered = BytesIO()
        qr_image.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Update booking with QR code
        booking.qr_code = qr_code_base64
        db.session.commit()

        # Store booking ID in session for confirmation page
        session['booking_id'] = booking.id

        return jsonify({
            'success': True,
            'redirect_url': url_for('booking_confirmation')
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        })

@app.route('/booking_confirmation')
def booking_confirmation():
    # Get the booking ID from session
    booking_id = session.get('booking_id')
    
    if not booking_id:
        flash('No booking found', 'error')
        return redirect(url_for('booking'))
    
    # Get the booking from database
    booking = get_booking_by_id(booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('booking'))
    
    # Convert QR code from base64 to data URL
    qr_code_url = f"data:image/png;base64,{booking.qr_code}" if booking.qr_code else None
    
    # Create a dictionary with booking and user information
    booking_dict = booking.to_dict()
    booking_dict['user'] = {
        'name': booking.user.name,
        'email': booking.user.email
    }
    
    return render_template('booking_confirmation.html',
                         booking=booking_dict,
                         qr_code=qr_code_url)

@app.route('/scan/<int:booking_id>')
def scan_result(booking_id):
    booking = get_booking_by_id(booking_id)
    if not booking:
        return "Invalid booking ID", 404
    
    # Check if the booking is valid (not expired)
    is_valid = booking.visit_date >= datetime.now().date()
    
    # Get monument image URL based on the monument name
    monument_images = {
        'Taj Mahal': 'https://source.unsplash.com/800x400/?taj-mahal',
        'Red Fort': 'https://source.unsplash.com/800x400/?red-fort-delhi',
        'Qutub Minar': 'https://source.unsplash.com/800x400/?qutub-minar'
    }
    monument_image = monument_images.get(booking.monument, 'https://source.unsplash.com/800x400/?india-monument')
    
    return render_template('scan_result.html',
                         booking=booking.to_dict(),
                         booking_id=booking_id,
                         is_valid=is_valid,
                         monument_image=monument_image)

@app.route('/get_parking_slots')
def get_parking_slots_route():
    monument = request.args.get('monument')
    date_str = request.args.get('date')
    vehicle_type = request.args.get('vehicle_type')
    
    if not monument or not date_str:
        return jsonify([])
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        slots = get_parking_slots(monument, date, vehicle_type)
        
        # Convert slots to JSON-serializable format
        slots_data = [
            {
                'number': slot.slot_number,
                'available': slot.is_available,
                'type': slot.vehicle_type,
                'id': slot.id
            }
            for slot in slots
        ]
        return jsonify(slots_data)
    except ValueError:
        return jsonify([])

@app.route('/parking', methods=['GET'])
def parking():
    return render_template('parking.html')

@app.route('/process_parking', methods=['POST'])
def process_parking():
    if request.method == 'POST':
        monument = request.form.get('monument')
        date_str = request.form.get('date')
        vehicle_type = request.form.get('vehicle_type')
        slot_id = request.form.get('slot_number')
        duration = int(request.form.get('duration', 2))
        vehicle_number = request.form.get('vehicle_number')
        driver_name = request.form.get('name')
        phone = request.form.get('phone')
        total_amount = float(request.form.get('total_amount', 0))
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Store parking details in session
            session['parking_details'] = {
                'monument': monument,
                'slot_id': slot_id,
                'vehicle_type': vehicle_type,
                'reservation_date': date_str,
                'duration': duration,
                'vehicle_number': vehicle_number,
                'driver_name': driver_name,
                'phone': phone,
                'amount': total_amount,
                'hourly_rate': 25
            }
            
            return redirect(url_for('payment_page', type='parking'))
                
        except ValueError:
            flash('Invalid date format')
        except Exception as e:
            flash(f'Error: {str(e)}')
        
        return redirect(url_for('parking'))

@app.route('/payment_page')
def payment_page():
    if 'user_id' not in session:
        flash('Please login to continue')
        return redirect(url_for('login'))

    booking_data = session.get('booking_data')
    if not booking_data:
        flash('No booking data found. Please make a booking first.')
        return redirect(url_for('booking'))

    return render_template('payment.html', booking=booking_data)

@app.route('/process_speech', methods=['POST'])
def process_speech():
    if not SPEECH_ENABLED:
        return jsonify({
            'success': False,
            'error': 'Speech recognition is not available'
        }), 503
        
    try:
        # Get audio file from request
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({
                'success': False,
                'error': 'No audio file received'
            }), 400

        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            audio_file.save(temp_audio.name)
            
            try:
                # Initialize recognizer
                recognizer = sr.Recognizer()
                
                # Load audio file
                with sr.AudioFile(temp_audio.name) as source:
                    audio_data = recognizer.record(source)
                    
                    try:
                        # Convert speech to text
                        text = recognizer.recognize_google(audio_data).lower()
                        
                        # Process commands
                        response = process_command(text)
                        
                        # Convert response to speech
                        tts = gTTS(text=response, lang='en')
                        
                        # Save response audio to temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_response:
                            tts.write_to_fp(temp_response.name)
                            
                            # Read response audio file and convert to base64
                            with open(temp_response.name, 'rb') as audio_file:
                                audio_data = base64.b64encode(audio_file.read()).decode('utf-8')
                            
                            # Clean up temporary files
                            os.unlink(temp_response.name)
                        
                        return jsonify({
                            'success': True,
                            'text': text,
                            'response': response,
                            'audio': audio_data
                        })
                        
                    except sr.UnknownValueError:
                        return jsonify({
                            'success': False,
                            'error': 'Could not understand audio'
                        }), 400
                    except sr.RequestError as e:
                        return jsonify({
                            'success': False,
                            'error': f'Could not request results: {str(e)}'
                        }), 503
                    
            finally:
                # Clean up temporary files
                os.unlink(temp_audio.name)
                
    except Exception as e:
        print(f"Speech processing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while processing speech'
        }), 500

def process_command(text):
    """Process voice commands and return appropriate response"""
    text = text.lower()
    
    # Navigation commands
    if 'home' in text:
        return 'Navigating to home page'
    elif 'booking' in text or 'book now' in text:
        return 'Opening booking form'
    elif 'parking' in text:
        return 'Opening parking reservation'
    elif 'logout' in text:
        return 'Logging out'
        
    # Form interactions
    elif 'student' in text:
        return 'Student discount will be applied'
    elif 'guide' in text:
        return 'Tour guide service added'
    elif 'need parking' in text:
        return 'Parking will be reserved'
    elif text.startswith('select '):
        monument = text.replace('select ', '')
        return f'Selected {monument}'
        
    # Default response
    return 'Command not recognized. Try saying "help" for available commands'

@app.route('/speech_help')
def speech_help():
    """Get help information about available voice commands"""
    help_text = {
        'commands': [
            {'command': 'Home', 'description': 'Go to home page'},
            {'command': 'Book Now', 'description': 'Go to booking page'},
            {'command': 'Parking', 'description': 'Go to parking page'},
            {'command': 'Logout', 'description': 'Log out'},
            {'command': 'I am a student', 'description': 'Apply student discount'},
            {'command': 'I need a guide', 'description': 'Add tour guide service'},
            {'command': 'I need parking', 'description': 'Add parking reservation'},
            {'command': 'Select [monument]', 'description': 'Choose a monument'},
            {'command': 'Help', 'description': 'Show available commands'}
        ],
        'shortcuts': [
            {'key': 'Alt + S', 'description': 'Start/Stop voice recognition'},
            {'key': 'Alt + H', 'description': 'Show help'}
        ]
    }
    return jsonify(help_text)

@app.route('/api/parking/slots')
def get_parking_slots_api():
    monument = request.args.get('monument')
    date_str = request.args.get('date')
    vehicle_type = request.args.get('vehicle_type', '4wheeler')  # Default to 4wheeler
    
    if not monument or not date_str:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        slots = get_parking_slots(monument, date, vehicle_type)
        
        # Convert slots to JSON-serializable format
        slots_data = []
        for slot in slots:
            slot_data = {
                'number': slot.slot_number,
                'available': True,
                'id': slot.id,
                'type': slot.vehicle_type
            }
            slots_data.append(slot_data)
            
        return jsonify(slots_data)
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    except Exception as e:
        print(f"Error getting parking slots: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/monument/<monument_name>')
def monument_details(monument_name):
    if monument_name not in MONUMENTS_DATA:
        flash('Monument not found')
        return redirect(url_for('home'))
    
    monument = MONUMENTS_DATA[monument_name]
    return render_template('monument_details.html', monument=monument)

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    if not SPEECH_ENABLED:
        return jsonify({
            'success': False,
            'error': 'Text-to-speech is not available'
        }), 503
        
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Create text-to-speech object
        tts = gTTS(text=text, lang='en', slow=False)
        
        # Save to BytesIO object
        audio_io = io.BytesIO()
        tts.write_to_fp(audio_io)
        audio_io.seek(0)
        
        # Return audio file
        return send_file(
            audio_io,
            mimetype='audio/mp3',
            as_attachment=True,
            download_name='monument_history.mp3'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process_parking_payment', methods=['POST'])
def process_parking_payment():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'error': 'Please login to complete the payment'
            })

        # Get form data with validation
        required_fields = ['monument', 'date', 'vehicle_type', 'vehicle_number', 
                         'driver_name', 'phone', 'slot_number', 'duration', 
                         'amount', 'payment_method']
        
        for field in required_fields:
            if not request.form.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                })

        # Parse and validate data
        try:
            date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            slot_number = int(request.form.get('slot_number'))
            duration = int(request.form.get('duration'))
            amount = float(request.form.get('amount'))
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid data format: {str(e)}'
            })

        # Create parking reservation
        try:
            reservation = ParkingReservation(
                user_id=session['user_id'],
                monument=request.form.get('monument'),
                slot_id=slot_number,
                vehicle_type=request.form.get('vehicle_type'),
                vehicle_number=request.form.get('vehicle_number'),
                driver_name=request.form.get('driver_name'),
                phone=request.form.get('phone'),
                reservation_date=date,
                duration=duration,
                amount=amount,
                payment_status='completed',
                payment_method=request.form.get('payment_method')
            )
            
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr_data = {
                'type': 'parking',
                'id': str(uuid.uuid4()),
                'monument': request.form.get('monument'),
                'date': date.strftime('%Y-%m-%d'),
                'slot': slot_number,
                'vehicle': request.form.get('vehicle_number')
            }
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            
            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            qr_img.save(buffered, format="PNG")
            qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            # Save QR code to reservation
            reservation.qr_code = qr_code_base64
            
            # Save to database
            db.session.add(reservation)
            db.session.commit()
            
            # Store reservation ID in session for confirmation page
            session['parking_reservation_id'] = reservation.id
            
            return jsonify({
                'success': True,
                'redirect_url': url_for('parking_confirmation')
            })
            
        except Exception as db_error:
            db.session.rollback()
            print(f"Database error: {str(db_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to save reservation. Please try again.'
            })
        
    except Exception as e:
        print(f"Payment processing error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Payment processing failed. Please try again.'
        })

@app.route('/parking-confirmation')
def parking_confirmation():
    try:
        reservation_id = session.get('parking_reservation_id')
        if not reservation_id:
            return redirect(url_for('parking'))
            
        reservation = ParkingReservation.query.get(reservation_id)
        if not reservation:
            return redirect(url_for('parking'))
            
        # Clear the reservation ID from session
        session.pop('parking_reservation_id', None)
        
        return render_template('parking_confirmation.html', 
                             reservation=reservation,
                             qr_code=reservation.qr_code)
                             
    except Exception as e:
        return redirect(url_for('parking'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()  # Roll back db session in case of errors
    return render_template('500.html'), 500

@app.route('/store_booking', methods=['POST'])
def store_booking():
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'error': 'Please login to continue'
        })

    try:
        booking_data = request.get_json()
        if not booking_data:
            return jsonify({
                'success': False,
                'error': 'Invalid booking data'
            })

        # Validate required fields
        required_fields = ['monument', 'date', 'time_slot', 'id_number']
        missing_fields = [field for field in required_fields if not booking_data.get(field)]
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            })

        # Store booking data in session
        session['booking_data'] = {
            'monument': booking_data['monument'],
            'date': booking_data['date'],
            'time_slot': booking_data['time_slot'],
            'num_visitors': booking_data.get('num_visitors', 0),
            'need_guide': booking_data.get('need_guide', False),
            'need_parking': booking_data.get('need_parking', False),
            'is_student': booking_data.get('is_student', False),
            'id_number': booking_data['id_number'],
            'camera_required': booking_data.get('camera_required', False),
            'name': booking_data.get('name'),
            'email': booking_data.get('email'),
            'age': booking_data.get('age'),
            'base_amount': booking_data.get('base_amount', 799),
            'final_amount': booking_data.get('final_amount', 799)
        }

        return jsonify({
            'success': True
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
