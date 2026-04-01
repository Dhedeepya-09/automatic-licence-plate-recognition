import sqlite3
import os
from datetime import datetime, timedelta
import pytz

IST = pytz.timezone('Asia/Kolkata')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'vehicle_system.db')

def init_db():
    """Initialize the database with tables and sample data."""
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # RTO Vehicles Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rto_vehicles (
            plate_number TEXT PRIMARY KEY,
            owner_name TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            registration_year INTEGER NOT NULL,
            puc_expiry DATE NOT NULL
        )
    ''')

    # Challans Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS challans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            violation_type TEXT NOT NULL,
            fine_amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plate_number) REFERENCES rto_vehicles(plate_number)
        )
    ''')

    # Seed Sample Data
    sample_vehicles = [
        ('MH12DE1234', 'John Doe', 'Car', 2015, '2023-12-31'),
        ('KA01AB4567', 'Jane Smith', 'Bus', 2005, '2025-06-30'), # Old vehicle (>15 years)
        ('DL3CAY9876', 'Mike Ross', 'Truck', 2018, '2022-01-01'), # Expired PUC
        ('HR26DQ1122', 'Sarah Connor', 'Bike', 2021, '2026-10-15'),
        ('UP16BT5566', 'Bruce Wayne', 'Car', 2019, '2024-03-01'), # Expired PUC (relative to today)
    ]

    cursor.executemany('''
        INSERT OR IGNORE INTO rto_vehicles (plate_number, owner_name, vehicle_type, registration_year, puc_expiry)
        VALUES (?, ?, ?, ?, ?)
    ''', sample_vehicles)

    conn.commit()
    conn.close()

def get_vehicle_details(plate_number):
    """Fetch vehicle details by plate number."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM rto_vehicles WHERE plate_number = ?', (plate_number,))
    result = cursor.fetchone()
    conn.close()
    return result

def add_or_update_vehicle(plate_number, owner_name, vehicle_type, registration_year, puc_expiry):
    """Add new or update existing vehicle details."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO rto_vehicles (plate_number, owner_name, vehicle_type, registration_year, puc_expiry)
        VALUES (?, ?, ?, ?, ?)
    ''', (plate_number, owner_name, vehicle_type, registration_year, puc_expiry))
    conn.commit()
    conn.close()

def delete_vehicle(plate_number):
    """Delete a vehicle from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rto_vehicles WHERE plate_number = ?', (plate_number,))
    conn.commit()
    conn.close()

def log_challan(plate_number, violation_type, fine_amount):
    """Log a generated challan if no identical one exists on the current calendar day (IST)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Use IST for all time calculations
    now_ist = datetime.now(IST)
    today_date = now_ist.strftime('%Y-%m-%d')
    timestamp_str = now_ist.strftime('%Y-%m-%d %H:%M:%S')

    # Strict De-duplication: Check if any challan exists for this plate & violation ON THIS DATE.
    # Using 'date(timestamp)' function in SQLite for calendar day comparison.
    cursor.execute('''
        SELECT id FROM challans 
        WHERE plate_number = ? AND violation_type = ? AND date(timestamp) = ?
    ''', (plate_number, violation_type, today_date))
    
    if cursor.fetchone() is None:
        cursor.execute('''
            INSERT INTO challans (plate_number, violation_type, fine_amount, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (plate_number, violation_type, fine_amount, timestamp_str))
        conn.commit()
    
    conn.close()

def get_all_vehicles():
    """Returns all vehicle records."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM rto_vehicles')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_challans():
    """Returns all challan records."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM challans ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
