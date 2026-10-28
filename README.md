# FireX – Smart Fire Escape System

## Overview
FireX is a fire emergency monitoring and evacuation support project designed to help monitor rooms, identify emergency situations, and support evacuation management.

## Features
- Room and people monitoring
- Fire emergency alerts
- Evacuation support dashboard
- Web-based interface
- Backend API for communicating with the database

## Technology Stack
- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, JavaScript
- **Database:** MySQL
- **Tools:** Git, GitHub

## Project Structure
```text
FireX-Smart-Fire-Escape-System/
├── backend/
│   ├── app.py
│   └── test_connection.py
├── frontend/
│   └── index.html
└── .gitignore
```

## Setup Instructions
1. Install Python and MySQL.
2. Create and configure the `firex` database and required tables.
3. Install the Python dependencies:
   `pip install flask flask-cors mysql-connector-python`
4. Configure the database connection in the backend.
5. Run the backend:
   `python app.py`
6. Open `frontend/index.html` in your browser.

## Note
Database setup and any required hardware integration must be configured separately. Refer to the source code for implementation details.
