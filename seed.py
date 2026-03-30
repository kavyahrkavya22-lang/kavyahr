"""Seed minimal users for local testing."""
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import os

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['spms']

def seed():
    # Check if users already exist
    if db.users.count_documents({}) > 0:
        print('Users already exist, skipping seed.')
        return
    
    admin = {'name': 'Admin', 'email': 'admin@spms.com', 'role': 'admin', 'password': generate_password_hash('admin123')}
    faculty = {'name': 'Dr. Faculty', 'email': 'faculty@spms.com', 'role': 'faculty', 'password': generate_password_hash('faculty123'), 'assigned_students': []}
    student = {'name': 'Student', 'email': 'student@spms.com', 'role': 'student', 'password': generate_password_hash('student123')}
    db.users.insert_many([admin, faculty, student])
    print('Seeded default users:')
    print('  Admin: admin@spms.com / admin123')
    print('  Faculty: faculty@spms.com / faculty123')
    print('  Student: student@spms.com / student123')

if __name__ == '__main__':
    seed()
