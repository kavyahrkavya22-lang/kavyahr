from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'zip', 'rar', 'pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx', 'xls', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MongoDB setup
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['spms']

def seed_default_users():
    """Create default admin and faculty users if they don't exist."""
    admin_email = 'admin@spms.com'
    faculty_email = 'faculty@spms.com'
    
    if not db.users.find_one({'email': admin_email}):
        admin = {
            'name': 'Admin',
            'email': admin_email,
            'role': 'admin',
            'password': generate_password_hash('admin123')
        }
        db.users.insert_one(admin)
        print(f'Created default admin: {admin_email} / admin123')
    
    if not db.users.find_one({'email': faculty_email}):
        faculty = {
            'name': 'Dr. Faculty',
            'email': faculty_email,
            'role': 'faculty',
            'password': generate_password_hash('faculty123'),
            'assigned_students': []
        }
        db.users.insert_one(faculty)
        print(f'Created default faculty: {faculty_email} / faculty123')

# Seed default users on startup
seed_default_users()

def get_user_by_email(email):
    return db.users.find_one({'email': email})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate password match
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('signup'))
        
        # Validate password length
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return redirect(url_for('signup'))
        
        # Check if user already exists
        if get_user_by_email(email):
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        
        # Create new user (default role is student)
        user = {
            'name': name,
            'email': email,
            'role': 'student',
            'password': generate_password_hash(password)
        }
        db.users.insert_one(user)
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    role = session.get('role')
    users = list(db.users.find())
    projects = list(db.projects.find())
    # Add student name to each project
    for proj in projects:
        student = db.users.find_one({'_id': ObjectId(proj['student_id'])})
        proj['student_name'] = student['name'] if student else 'Unknown'
    if role == 'admin':
        return render_template('dashboard_admin.html', users=users, projects=projects)
    elif role == 'faculty':
        # Show all student projects to faculty for review
        all_projects = list(db.projects.find())
        # Add student name to each project
        for proj in all_projects:
            student = db.users.find_one({'_id': ObjectId(proj['student_id'])})
            proj['student_name'] = student['name'] if student else 'Unknown'
        return render_template('dashboard_faculty.html', projects=all_projects)
    else:
        student_projects = list(db.projects.find({'student_id': session['user_id']}))
        return render_template('dashboard_student.html', projects=student_projects)

@app.route('/submit', methods=['GET', 'POST'])
def submit_project():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Handle file upload
        file_path = None
        if 'project_file' in request.files:
            file = request.files['project_file']
            if file and file.filename and allowed_file(file.filename):
                # Create unique filename to avoid conflicts
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{session['user_id']}_{int(__import__('time').time())}.{ext}"
                file_path = f"/static/uploads/{unique_filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        
        proj = {
            'student_id': session['user_id'],
            'register_number': request.form['register_number'],
            'course': request.form['course'],
            'title': request.form['title'],
            'technology': request.form['technology'],
            'guide': request.form.get('guide', ''),
            'description': request.form['description'],
            'project_file': file_path,
            'original_filename': file.filename if file and file.filename else None,
            'status': 'Submitted',
            'feedback': None,
            'marks': None
        }
        db.projects.insert_one(proj)
        flash('Project submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('submit.html')

@app.route('/review/<project_id>', methods=['GET', 'POST'])
def review(project_id):
    if 'user_id' not in session or session.get('role') not in ['faculty', 'admin']:
        return redirect(url_for('login'))
    proj = db.projects.find_one({'_id': ObjectId(project_id)})
    # Get student details
    if proj:
        student = db.users.find_one({'_id': ObjectId(proj['student_id'])})
        proj['student_name'] = student['name'] if student else 'Unknown'
    if request.method == 'POST':
        status = request.form['status']
        feedback = request.form['feedback']
        marks = request.form.get('marks')
        db.projects.update_one({'_id': ObjectId(project_id)}, {'$set': {'status': status, 'feedback': feedback, 'marks': marks}})
        flash('Review saved', 'success')
        return redirect(url_for('dashboard'))
    return render_template('review.html', proj=proj)

@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        # create user
        user = {
            'name': request.form['name'],
            'email': request.form['email'],
            'role': request.form['role'],
            'password': generate_password_hash(request.form['password'])
        }
        db.users.insert_one(user)
        flash('User created', 'success')
    users = list(db.users.find())
    return render_template('admin_users.html', users=users)

@app.route('/admin/assign-student', methods=['POST'])
def assign_student():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    faculty_id = request.form.get('faculty_id')
    student_id = request.form.get('student_id')
    
    # Add student to faculty's assigned_students
    faculty = db.users.find_one({'_id': ObjectId(faculty_id)})
    if faculty:
        assigned = faculty.get('assigned_students', [])
        if student_id not in assigned:
            assigned.append(student_id)
            db.users.update_one({'_id': ObjectId(faculty_id)}, {'$set': {'assigned_students': assigned}})
            flash('Student assigned to faculty successfully', 'success')
        else:
            flash('Student is already assigned to this faculty', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/admin/edit-assignment/<faculty_id>', methods=['GET', 'POST'])
def edit_assignment(faculty_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    faculty = db.users.find_one({'_id': ObjectId(faculty_id)})
    all_students = list(db.users.find({'role': 'student'}))
    
    if request.method == 'POST':
        assigned_students = request.form.getlist('assigned_students')
        db.users.update_one({'_id': ObjectId(faculty_id)}, {'$set': {'assigned_students': assigned_students}})
        flash('Assignment updated successfully', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('edit_assignment.html', faculty=faculty, students=all_students)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    
    # Get user statistics based on role
    stats = {}
    projects = []
    if user['role'] == 'student':
        projects = list(db.projects.find({'student_id': session['user_id']}))
        stats['total_projects'] = len(projects)
        stats['submitted'] = len([p for p in projects if p['status'] == 'Submitted'])
        stats['approved'] = len([p for p in projects if p['status'] == 'Approved'])
        stats['rejected'] = len([p for p in projects if p['status'] == 'Rejected'])
    elif user['role'] == 'faculty':
        assigned = user.get('assigned_students', [])
        stats['assigned_students'] = len(assigned)
        # Get all projects from assigned students
        student_projects = []
        for student_id in assigned:
            proj = list(db.projects.find({'student_id': student_id}))
            student_projects.extend(proj)
        projects = student_projects
        stats['total_reviews'] = len(student_projects)
        stats['pending'] = len([p for p in student_projects if p['status'] == 'Submitted'])
        stats['reviewed'] = len([p for p in student_projects if p['status'] in ['Approved', 'Rejected']])
    elif user['role'] == 'admin':
        stats['total_users'] = db.users.count_documents({})
        stats['total_students'] = db.users.count_documents({'role': 'student'})
        stats['total_faculty'] = db.users.count_documents({'role': 'faculty'})
        stats['total_projects'] = db.projects.count_documents({})
        projects = list(db.projects.find())
    
    # Handle profile update
    if request.method == 'POST':
        name = request.form.get('name')
        new_password = request.form.get('new_password')
        
        if name:
            db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': {'name': name}})
            flash('Profile updated successfully', 'success')
        
        if new_password:
            db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': {'password': generate_password_hash(new_password)}})
            flash('Password updated successfully', 'success')
        
        # Refresh user data
        user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    
    return render_template('profile.html', user=user, stats=stats, projects=projects)

@app.route('/user/<user_id>')
def view_user_profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user has permission to view profiles
    current_role = session.get('role')
    if current_role not in ['admin', 'faculty']:
        flash('You do not have permission to view user profiles', 'danger')
        return redirect(url_for('dashboard'))
    
    target_user = db.users.find_one({'_id': ObjectId(user_id)})
    if not target_user:
        flash('User not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get user statistics
    user_stats = {}
    if target_user['role'] == 'student':
        projects = list(db.projects.find({'student_id': user_id}))
        user_stats['total_projects'] = len(projects)
        user_stats['submitted'] = len([p for p in projects if p['status'] == 'Submitted'])
        user_stats['approved'] = len([p for p in projects if p['status'] == 'Approved'])
        user_stats['rejected'] = len([p for p in projects if p['status'] == 'Rejected'])
    elif target_user['role'] == 'faculty':
        assigned = target_user.get('assigned_students', [])
        user_stats['assigned_students'] = len(assigned)
    
    return render_template('profile.html', user=target_user, stats=user_stats, is_viewing_other=True)

if __name__ == '__main__':
    app.run(debug=True)
