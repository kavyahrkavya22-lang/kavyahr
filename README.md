# Student Project Management System (SPMS)

Flask application with MongoDB for Admin/Faculty/Student project management flows.

## Quick Start

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Ensure MongoDB is running locally or set `MONGO_URI` environment variable.

3. Run the app:

```bash
python app.py
```

## Default Credentials

The system auto-creates these default users on first run:

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@spms.com | admin123 |
| Faculty | faculty@spms.com | faculty123 |

**Note:** Students can self-register via the Sign Up page.

## Database

- Default MongoDB: `mongodb://localhost:27017/`
- Database name: `spms`

## Features

- **Admin:** Manage all users and projects, view statistics
- **Faculty:** Review assigned student projects with marks and feedback
- **Students:** Submit projects with details (register number, course, guide)
