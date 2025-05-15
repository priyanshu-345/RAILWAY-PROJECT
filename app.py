from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import random
import hashlib
from functools import wraps
from io import BytesIO

try:
    from flask_weasyprint import HTML, render_pdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("WeasyPrint not installed. PDF generation will be disabled.")

try:
    from pymongo import MongoClient
    from bson.objectid import ObjectId
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    print("PyMongo not installed. Will use local JSON data.")

app = Flask(__name__)
app.secret_key = 'railway_secret_key'

# Global variable for data paths
data_dir = Path('data')

# Global variable to track if we're using MongoDB or JSON
using_mongodb = False

# MongoDB connection
client = None
db = None

def connect_to_mongodb():
    global client, db, using_mongodb
    
    if not MONGODB_AVAILABLE:
        return False
    
    try:
        # Try connecting to MongoDB Atlas first
        try:
            print("Trying to connect to MongoDB Atlas...")
            atlas_uri = "mongodb+srv://railway:railway123@railway-cluster.mongodb.net/railway_db?retryWrites=true&w=majority"
            client = MongoClient(atlas_uri, serverSelectionTimeoutMS=5000)
            client.server_info()  # Will raise an exception if connection fails
            db = client['railway_db']
            using_mongodb = True
            print("Connected to MongoDB Atlas successfully!")
            return True
        except Exception as atlas_error:
            print(f"MongoDB Atlas connection failed: {atlas_error}")
            print("Trying local MongoDB instead...")
            
            # If Atlas fails, try connecting to local MongoDB
            local_uri = "mongodb://localhost:27017/"
            client = MongoClient(local_uri, serverSelectionTimeoutMS=5000)
            client.server_info()  # Will raise an exception if connection fails
            db = client['railway_db']
            using_mongodb = True
            print("Connected to local MongoDB successfully!")
            return True
            
    except Exception as e:
        print(f"All MongoDB connection attempts failed: {e}")
        return False

# Function to load and setup JSON data
def load_json_data():
    """Load data from JSON files or create them if they don't exist"""
    data_dir.mkdir(exist_ok=True)
    
    # Sample data structures
    data = {
        'stations': [
            {"code": "NDLS", "name": "New Delhi"},
            {"code": "BCT", "name": "Mumbai Central"},
            {"code": "HWH", "name": "Howrah"},
            {"code": "SBC", "name": "Bangalore City"},
            {"code": "MMCT", "name": "Mumbai Central"}
        ],
        'trains': [
            {
                "number": "12951",
                "name": "Rajdhani Express",
                "source": "NDLS",
                "source_code": "NDLS",
                "destination": "BCT",
                "destination_code": "BCT",
                "days": ["Mon", "Wed", "Fri"],
                "classes": ["1A", "2A", "3A"],
                "speed": "130",
                "stations": [
                    {"code": "NDLS", "arrival": "", "departure": "16:25", "day": 1, "distance": 0, "platform": "1"},
                    {"code": "BCT", "arrival": "08:15", "departure": "", "day": 2, "distance": 1384, "platform": "3"}
                ],
                "seats": {
                    "1A": 20,
                    "2A": 50,
                    "3A": 100
                }
            },
            {
                "number": "12953",
                "name": "Duronto Express",
                "source": "NDLS",
                "source_code": "NDLS",
                "destination": "HWH",
                "destination_code": "HWH",
                "days": ["Tue", "Thu", "Sat"],
                "classes": ["1A", "2A", "3A", "SL"],
                "speed": "120",
                "stations": [
                    {"code": "NDLS", "arrival": "", "departure": "22:00", "day": 1, "distance": 0, "platform": "5"},
                    {"code": "HWH", "arrival": "10:30", "departure": "", "day": 2, "distance": 1447, "platform": "9"}
                ],
                "seats": {
                    "1A": 15,
                    "2A": 40,
                    "3A": 80,
                    "SL": 150
                }
            }
        ],
        'bookings': [],
        'users': []
    }
    
    # Create JSON files if they don't exist
    for key, value in data.items():
        file_path = data_dir / f"{key}.json"
        if not file_path.exists():
            with open(file_path, 'w') as f:
                json.dump(value, f, indent=2)
    
    return data

# Helper functions for JSON data
def get_json_data(collection):
    file_path = data_dir / f"{collection}.json"
    if file_path.exists():
        with open(file_path, 'r') as f:
            return json.load(f)
    return []

def save_json_data(collection, data):
    file_path = data_dir / f"{collection}.json"
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

# Generic database operations that work with either MongoDB or JSON
def find_one(collection, query):
    if using_mongodb:
        return db[collection].find_one(query)
    else:
        data = get_json_data(collection)
        for item in data:
            match = True
            for key, value in query.items():
                if key.startswith('$or'):
                    or_match = False
                    for or_clause in value:
                        clause_match = True
                        for or_key, or_value in or_clause.items():
                            if or_key not in item or item[or_key] != or_value:
                                clause_match = False
                                break
                        if clause_match:
                            or_match = True
                            break
                    if not or_match:
                        match = False
                        break
                elif key not in item or item[key] != value:
                    match = False
                    break
            if match:
                return item
        return None

def find(collection, query=None):
    if using_mongodb:
        return list(db[collection].find(query or {}))
    else:
        data = get_json_data(collection)
        if query is None:
            return data
        
        results = []
        for item in data:
            match = True
            for key, value in query.items():
                if key not in item or item[key] != value:
                    match = False
                    break
            if match:
                results.append(item)
        return results

def insert_one(collection, document):
    if using_mongodb:
        result = db[collection].insert_one(document)
        return str(result.inserted_id)
    else:
        data = get_json_data(collection)
        
        # Add ID if not present
        if '_id' not in document:
            document['_id'] = str(random.randint(1000000, 9999999))
        
        data.append(document)
        save_json_data(collection, data)
        return document['_id']

def insert_many(collection, documents):
    if using_mongodb:
        db[collection].insert_many(documents)
    else:
        data = get_json_data(collection)
        
        # Add IDs if not present
        for doc in documents:
            if '_id' not in doc:
                doc['_id'] = str(random.randint(1000000, 9999999))
            data.append(doc)
            
        save_json_data(collection, data)

def count_documents(collection, query=None):
    if using_mongodb:
        return db[collection].count_documents(query or {})
    else:
        return len(find(collection, query))

# Initialize database with sample data if empty
def init_db():
    # Try to connect to MongoDB first
    if connect_to_mongodb():
        # If connected to MongoDB, check if collections are empty and initialize if needed
        if count_documents('stations') == 0:
            sample_stations = [
                {"code": "NDLS", "name": "New Delhi"},
                {"code": "BCT", "name": "Mumbai Central"},
                {"code": "HWH", "name": "Howrah"},
                {"code": "SBC", "name": "Bangalore City"},
                {"code": "MMCT", "name": "Mumbai Central"},
                {"code": "MAS", "name": "Chennai Central"},
                {"code": "PUNE", "name": "Pune Junction"},
                {"code": "ADI", "name": "Ahmedabad Junction"},
                {"code": "BPL", "name": "Bhopal Junction"},
                {"code": "KOTA", "name": "Kota Junction"},
                {"code": "AGC", "name": "Agra Cantt"},
                {"code": "CNB", "name": "Kanpur Central"},
                {"code": "ALD", "name": "Allahabad Junction"},
                {"code": "BSB", "name": "Varanasi Junction"},
                {"code": "TATA", "name": "Tatanagar Junction"},
                {"code": "PNBE", "name": "Patna Junction"},
                {"code": "RNC", "name": "Ranchi Junction"},
                {"code": "KOL", "name": "Kolkata Junction"},
                {"code": "JPR", "name": "Jaipur Junction"},
                {"code": "UDZ", "name": "Udaipur City"},
                {"code": "JU", "name": "Jodhpur Junction"},
                {"code": "JAT", "name": "Jammu Tawi"},
                {"code": "CDG", "name": "Chandigarh Junction"},
                {"code": "LKO", "name": "Lucknow Junction"},
                {"code": "GHY", "name": "Guwahati"},
                {"code": "SC", "name": "Secunderabad Junction"},
                {"code": "HYD", "name": "Hyderabad Deccan"},
                {"code": "MAO", "name": "Madgaon Junction"},
                {"code": "TVC", "name": "Thiruvananthapuram Central"},
                {"code": "ERS", "name": "Ernakulam Junction"},
                {"code": "MYS", "name": "Mysuru Junction"},
                {"code": "VSKP", "name": "Visakhapatnam Junction"}
            ]
            insert_many('stations', sample_stations)
        
        if count_documents('trains') == 0:
            sample_trains = [
                {
                    "number": "12951",
                    "name": "Rajdhani Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "BCT",
                    "destination_code": "BCT",
                    "days": ["Mon", "Wed", "Fri"],
                    "classes": ["1A", "2A", "3A"],
                    "speed": "130",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "16:25", "day": 1, "distance": 0, "platform": "1"},
                        {"code": "BCT", "arrival": "08:15", "departure": "", "day": 2, "distance": 1384, "platform": "3"}
                    ],
                    "seats": {
                        "1A": 20,
                        "2A": 50,
                        "3A": 100
                    }
                },
                {
                    "number": "12953",
                    "name": "Duronto Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "HWH",
                    "destination_code": "HWH",
                    "days": ["Tue", "Thu", "Sat"],
                    "classes": ["1A", "2A", "3A", "SL"],
                    "speed": "120",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "22:00", "day": 1, "distance": 0, "platform": "5"},
                        {"code": "HWH", "arrival": "10:30", "departure": "", "day": 2, "distance": 1447, "platform": "9"}
                    ],
                    "seats": {
                        "1A": 15,
                        "2A": 40,
                        "3A": 80,
                        "SL": 150
                    }
                },
                {
                    "number": "12301",
                    "name": "Karnataka Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "SBC",
                    "destination_code": "SBC",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "110",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "20:15", "day": 1, "distance": 0, "platform": "7"},
                        {"code": "BPL", "arrival": "06:20", "departure": "06:30", "day": 2, "distance": 702, "platform": "1"},
                        {"code": "SBC", "arrival": "08:30", "departure": "", "day": 3, "distance": 2349, "platform": "5"}
                    ],
                    "seats": {
                        "2A": 45,
                        "3A": 110,
                        "SL": 280
                    }
                },
                {
                    "number": "12259",
                    "name": "Shatabdi Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "LKO",
                    "destination_code": "LKO",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                    "classes": ["CC", "EC"],
                    "speed": "140",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "06:10", "day": 1, "distance": 0, "platform": "3"},
                        {"code": "CNB", "arrival": "10:25", "departure": "10:30", "day": 1, "distance": 435, "platform": "1"},
                        {"code": "LKO", "arrival": "12:40", "departure": "", "day": 1, "distance": 511, "platform": "2"}
                    ],
                    "seats": {
                        "CC": 400,
                        "EC": 50
                    }
                },
                {
                    "number": "12216",
                    "name": "Garib Rath Express",
                    "source": "MAS",
                    "source_code": "MAS",
                    "destination": "PNBE",
                    "destination_code": "PNBE",
                    "days": ["Wed", "Fri", "Sun"],
                    "classes": ["3A"],
                    "speed": "90",
                    "stations": [
                        {"code": "MAS", "arrival": "", "departure": "15:45", "day": 1, "distance": 0, "platform": "4"},
                        {"code": "SC", "arrival": "04:30", "departure": "04:45", "day": 2, "distance": 700, "platform": "5"},
                        {"code": "BSB", "arrival": "13:50", "departure": "14:00", "day": 3, "distance": 1950, "platform": "6"},
                        {"code": "PNBE", "arrival": "17:15", "departure": "", "day": 3, "distance": 2175, "platform": "1"}
                    ],
                    "seats": {
                        "3A": 350
                    }
                },
                {
                    "number": "12019",
                    "name": "Howrah Shatabdi",
                    "source": "HWH",
                    "source_code": "HWH",
                    "destination": "RNC",
                    "destination_code": "RNC",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                    "classes": ["CC", "EC"],
                    "speed": "120",
                    "stations": [
                        {"code": "HWH", "arrival": "", "departure": "06:05", "day": 1, "distance": 0, "platform": "9"},
                        {"code": "TATA", "arrival": "08:55", "departure": "09:00", "day": 1, "distance": 244, "platform": "1"},
                        {"code": "RNC", "arrival": "11:55", "departure": "", "day": 1, "distance": 419, "platform": "1"}
                    ],
                    "seats": {
                        "CC": 380,
                        "EC": 40
                    }
                },
                {
                    "number": "12628",
                    "name": "Karnataka Express",
                    "source": "SBC",
                    "source_code": "SBC",
                    "destination": "NDLS",
                    "destination_code": "NDLS",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "classes": ["1A", "2A", "3A", "SL"],
                    "speed": "110",
                    "stations": [
                        {"code": "SBC", "arrival": "", "departure": "19:20", "day": 1, "distance": 0, "platform": "6"},
                        {"code": "MYS", "arrival": "21:15", "departure": "21:20", "day": 1, "distance": 139, "platform": "1"},
                        {"code": "PUNE", "arrival": "13:30", "departure": "13:40", "day": 2, "distance": 836, "platform": "2"},
                        {"code": "NDLS", "arrival": "06:40", "departure": "", "day": 3, "distance": 2349, "platform": "8"}
                    ],
                    "seats": {
                        "1A": 24,
                        "2A": 48,
                        "3A": 96,
                        "SL": 240
                    }
                },
                {
                    "number": "12471",
                    "name": "Swaraj Express",
                    "source": "JAT",
                    "source_code": "JAT",
                    "destination": "BCT",
                    "destination_code": "BCT",
                    "days": ["Tue", "Thu", "Sat"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "100",
                    "stations": [
                        {"code": "JAT", "arrival": "", "departure": "12:40", "day": 1, "distance": 0, "platform": "3"},
                        {"code": "CDG", "arrival": "15:15", "departure": "15:20", "day": 1, "distance": 160, "platform": "4"},
                        {"code": "JPR", "arrival": "22:45", "departure": "22:55", "day": 1, "distance": 580, "platform": "1"},
                        {"code": "ADI", "arrival": "07:30", "departure": "07:40", "day": 2, "distance": 986, "platform": "3"},
                        {"code": "BCT", "arrival": "15:20", "departure": "", "day": 2, "distance": 1277, "platform": "5"}
                    ],
                    "seats": {
                        "2A": 46,
                        "3A": 112,
                        "SL": 280
                    }
                },
                {
                    "number": "12907",
                    "name": "Sampark Kranti Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "SC",
                    "destination_code": "SC",
                    "days": ["Mon", "Wed", "Fri"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "110",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "07:20", "day": 1, "distance": 0, "platform": "4"},
                        {"code": "AGC", "arrival": "09:45", "departure": "09:50", "day": 1, "distance": 196, "platform": "2"},
                        {"code": "BPL", "arrival": "18:25", "departure": "18:35", "day": 1, "distance": 703, "platform": "3"},
                        {"code": "SC", "arrival": "15:45", "departure": "", "day": 2, "distance": 1661, "platform": "1"}
                    ],
                    "seats": {
                        "2A": 48,
                        "3A": 124,
                        "SL": 320
                    }
                },
                {
                    "number": "12295",
                    "name": "Sanghamitra Express",
                    "source": "ERS",
                    "source_code": "ERS",
                    "destination": "HWH",
                    "destination_code": "HWH",
                    "days": ["Tue", "Thu", "Sun"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "105",
                    "stations": [
                        {"code": "ERS", "arrival": "", "departure": "11:25", "day": 1, "distance": 0, "platform": "1"},
                        {"code": "TVC", "arrival": "15:45", "departure": "15:55", "day": 1, "distance": 218, "platform": "2"},
                        {"code": "MAS", "arrival": "06:30", "departure": "06:45", "day": 2, "distance": 747, "platform": "5"},
                        {"code": "VSKP", "arrival": "19:30", "departure": "19:40", "day": 2, "distance": 1116, "platform": "3"},
                        {"code": "HWH", "arrival": "16:05", "departure": "", "day": 3, "distance": 2066, "platform": "12"}
                    ],
                    "seats": {
                        "2A": 44,
                        "3A": 108,
                        "SL": 264
                    }
                }
            ]
            insert_many('trains', sample_trains)
    else:
        # If MongoDB connection failed, use local JSON data
        print("Using local JSON data storage")
        load_json_data()
        
        # Add the same stations to JSON data
        current_stations = get_json_data('stations')
        if len(current_stations) <= 5:  # Check if we only have the default stations
            updated_stations = [
                {"code": "NDLS", "name": "New Delhi"},
                {"code": "BCT", "name": "Mumbai Central"},
                {"code": "HWH", "name": "Howrah"},
                {"code": "SBC", "name": "Bangalore City"},
                {"code": "MMCT", "name": "Mumbai Central"},
                {"code": "MAS", "name": "Chennai Central"},
                {"code": "PUNE", "name": "Pune Junction"},
                {"code": "ADI", "name": "Ahmedabad Junction"},
                {"code": "BPL", "name": "Bhopal Junction"},
                {"code": "KOTA", "name": "Kota Junction"},
                {"code": "AGC", "name": "Agra Cantt"},
                {"code": "CNB", "name": "Kanpur Central"},
                {"code": "ALD", "name": "Allahabad Junction"},
                {"code": "BSB", "name": "Varanasi Junction"},
                {"code": "TATA", "name": "Tatanagar Junction"},
                {"code": "PNBE", "name": "Patna Junction"},
                {"code": "RNC", "name": "Ranchi Junction"},
                {"code": "KOL", "name": "Kolkata Junction"},
                {"code": "JPR", "name": "Jaipur Junction"},
                {"code": "UDZ", "name": "Udaipur City"},
                {"code": "JU", "name": "Jodhpur Junction"},
                {"code": "JAT", "name": "Jammu Tawi"},
                {"code": "CDG", "name": "Chandigarh Junction"},
                {"code": "LKO", "name": "Lucknow Junction"},
                {"code": "GHY", "name": "Guwahati"},
                {"code": "SC", "name": "Secunderabad Junction"},
                {"code": "HYD", "name": "Hyderabad Deccan"},
                {"code": "MAO", "name": "Madgaon Junction"},
                {"code": "TVC", "name": "Thiruvananthapuram Central"},
                {"code": "ERS", "name": "Ernakulam Junction"},
                {"code": "MYS", "name": "Mysuru Junction"},
                {"code": "VSKP", "name": "Visakhapatnam Junction"}
            ]
            save_json_data('stations', updated_stations)

        # Add more trains to JSON data
        current_trains = get_json_data('trains')
        if len(current_trains) <= 2:  # Check if we only have the default trains
            # Add the same trains to JSON data
            updated_trains = [
                # Copy the same trains array from above
                {
                    "number": "12951",
                    "name": "Rajdhani Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "BCT",
                    "destination_code": "BCT",
                    "days": ["Mon", "Wed", "Fri"],
                    "classes": ["1A", "2A", "3A"],
                    "speed": "130",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "16:25", "day": 1, "distance": 0, "platform": "1"},
                        {"code": "BCT", "arrival": "08:15", "departure": "", "day": 2, "distance": 1384, "platform": "3"}
                    ],
                    "seats": {
                        "1A": 20,
                        "2A": 50,
                        "3A": 100
                    }
                },
                {
                    "number": "12953",
                    "name": "Duronto Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "HWH",
                    "destination_code": "HWH",
                    "days": ["Tue", "Thu", "Sat"],
                    "classes": ["1A", "2A", "3A", "SL"],
                    "speed": "120",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "22:00", "day": 1, "distance": 0, "platform": "5"},
                        {"code": "HWH", "arrival": "10:30", "departure": "", "day": 2, "distance": 1447, "platform": "9"}
                    ],
                    "seats": {
                        "1A": 15,
                        "2A": 40,
                        "3A": 80,
                        "SL": 150
                    }
                },
                {
                    "number": "12301",
                    "name": "Karnataka Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "SBC",
                    "destination_code": "SBC",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "110",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "20:15", "day": 1, "distance": 0, "platform": "7"},
                        {"code": "BPL", "arrival": "06:20", "departure": "06:30", "day": 2, "distance": 702, "platform": "1"},
                        {"code": "SBC", "arrival": "08:30", "departure": "", "day": 3, "distance": 2349, "platform": "5"}
                    ],
                    "seats": {
                        "2A": 45,
                        "3A": 110,
                        "SL": 280
                    }
                },
                {
                    "number": "12259",
                    "name": "Shatabdi Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "LKO",
                    "destination_code": "LKO",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                    "classes": ["CC", "EC"],
                    "speed": "140",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "06:10", "day": 1, "distance": 0, "platform": "3"},
                        {"code": "CNB", "arrival": "10:25", "departure": "10:30", "day": 1, "distance": 435, "platform": "1"},
                        {"code": "LKO", "arrival": "12:40", "departure": "", "day": 1, "distance": 511, "platform": "2"}
                    ],
                    "seats": {
                        "CC": 400,
                        "EC": 50
                    }
                },
                {
                    "number": "12216",
                    "name": "Garib Rath Express",
                    "source": "MAS",
                    "source_code": "MAS",
                    "destination": "PNBE",
                    "destination_code": "PNBE",
                    "days": ["Wed", "Fri", "Sun"],
                    "classes": ["3A"],
                    "speed": "90",
                    "stations": [
                        {"code": "MAS", "arrival": "", "departure": "15:45", "day": 1, "distance": 0, "platform": "4"},
                        {"code": "SC", "arrival": "04:30", "departure": "04:45", "day": 2, "distance": 700, "platform": "5"},
                        {"code": "BSB", "arrival": "13:50", "departure": "14:00", "day": 3, "distance": 1950, "platform": "6"},
                        {"code": "PNBE", "arrival": "17:15", "departure": "", "day": 3, "distance": 2175, "platform": "1"}
                    ],
                    "seats": {
                        "3A": 350
                    }
                },
                {
                    "number": "12019",
                    "name": "Howrah Shatabdi",
                    "source": "HWH",
                    "source_code": "HWH",
                    "destination": "RNC",
                    "destination_code": "RNC",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                    "classes": ["CC", "EC"],
                    "speed": "120",
                    "stations": [
                        {"code": "HWH", "arrival": "", "departure": "06:05", "day": 1, "distance": 0, "platform": "9"},
                        {"code": "TATA", "arrival": "08:55", "departure": "09:00", "day": 1, "distance": 244, "platform": "1"},
                        {"code": "RNC", "arrival": "11:55", "departure": "", "day": 1, "distance": 419, "platform": "1"}
                    ],
                    "seats": {
                        "CC": 380,
                        "EC": 40
                    }
                },
                {
                    "number": "12628",
                    "name": "Karnataka Express",
                    "source": "SBC",
                    "source_code": "SBC",
                    "destination": "NDLS",
                    "destination_code": "NDLS",
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "classes": ["1A", "2A", "3A", "SL"],
                    "speed": "110",
                    "stations": [
                        {"code": "SBC", "arrival": "", "departure": "19:20", "day": 1, "distance": 0, "platform": "6"},
                        {"code": "MYS", "arrival": "21:15", "departure": "21:20", "day": 1, "distance": 139, "platform": "1"},
                        {"code": "PUNE", "arrival": "13:30", "departure": "13:40", "day": 2, "distance": 836, "platform": "2"},
                        {"code": "NDLS", "arrival": "06:40", "departure": "", "day": 3, "distance": 2349, "platform": "8"}
                    ],
                    "seats": {
                        "1A": 24,
                        "2A": 48,
                        "3A": 96,
                        "SL": 240
                    }
                },
                {
                    "number": "12471",
                    "name": "Swaraj Express",
                    "source": "JAT",
                    "source_code": "JAT",
                    "destination": "BCT",
                    "destination_code": "BCT",
                    "days": ["Tue", "Thu", "Sat"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "100",
                    "stations": [
                        {"code": "JAT", "arrival": "", "departure": "12:40", "day": 1, "distance": 0, "platform": "3"},
                        {"code": "CDG", "arrival": "15:15", "departure": "15:20", "day": 1, "distance": 160, "platform": "4"},
                        {"code": "JPR", "arrival": "22:45", "departure": "22:55", "day": 1, "distance": 580, "platform": "1"},
                        {"code": "ADI", "arrival": "07:30", "departure": "07:40", "day": 2, "distance": 986, "platform": "3"},
                        {"code": "BCT", "arrival": "15:20", "departure": "", "day": 2, "distance": 1277, "platform": "5"}
                    ],
                    "seats": {
                        "2A": 46,
                        "3A": 112,
                        "SL": 280
                    }
                },
                {
                    "number": "12907",
                    "name": "Sampark Kranti Express",
                    "source": "NDLS",
                    "source_code": "NDLS",
                    "destination": "SC",
                    "destination_code": "SC",
                    "days": ["Mon", "Wed", "Fri"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "110",
                    "stations": [
                        {"code": "NDLS", "arrival": "", "departure": "07:20", "day": 1, "distance": 0, "platform": "4"},
                        {"code": "AGC", "arrival": "09:45", "departure": "09:50", "day": 1, "distance": 196, "platform": "2"},
                        {"code": "BPL", "arrival": "18:25", "departure": "18:35", "day": 1, "distance": 703, "platform": "3"},
                        {"code": "SC", "arrival": "15:45", "departure": "", "day": 2, "distance": 1661, "platform": "1"}
                    ],
                    "seats": {
                        "2A": 48,
                        "3A": 124,
                        "SL": 320
                    }
                },
                {
                    "number": "12295",
                    "name": "Sanghamitra Express",
                    "source": "ERS",
                    "source_code": "ERS",
                    "destination": "HWH",
                    "destination_code": "HWH",
                    "days": ["Tue", "Thu", "Sun"],
                    "classes": ["2A", "3A", "SL"],
                    "speed": "105",
                    "stations": [
                        {"code": "ERS", "arrival": "", "departure": "11:25", "day": 1, "distance": 0, "platform": "1"},
                        {"code": "TVC", "arrival": "15:45", "departure": "15:55", "day": 1, "distance": 218, "platform": "2"},
                        {"code": "MAS", "arrival": "06:30", "departure": "06:45", "day": 2, "distance": 747, "platform": "5"},
                        {"code": "VSKP", "arrival": "19:30", "departure": "19:40", "day": 2, "distance": 1116, "platform": "3"},
                        {"code": "HWH", "arrival": "16:05", "departure": "", "day": 3, "distance": 2066, "platform": "12"}
                    ],
                    "seats": {
                        "2A": 44,
                        "3A": 108,
                        "SL": 264
                    }
                }
            ]
            save_json_data('trains', updated_trains)

# User authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/train_schedule', methods=['GET', 'POST'])
def train_schedule():
    if request.method == 'POST':
        train_number = request.form.get('train_number', '').strip()
        
        if not train_number:
            flash('Please enter a train number', 'error')
            return redirect(url_for('train_schedule'))
        
        # Debug log
        print(f"Searching for train number: '{train_number}'")
        
        # Find train in data
        train = find_one('trains', {"number": train_number})
        
        if not train:
            # If not found, check trains data directly
            all_trains = get_json_data('trains')
            print(f"Available trains: {[t['number'] for t in all_trains]}")
            
            flash(f'Train {train_number} not found. Please check the train number and try again.', 'error')
            return redirect(url_for('train_schedule'))
        
        # Get station names for each station code
        all_stations = get_json_data('stations')
        station_details = []
        
        for station in train['stations']:
            found_station = False
            for station_doc in all_stations:
                if station_doc['code'] == station['code']:
                    station_info = station.copy()
                    station_info['name'] = station_doc['name']
                    station_details.append(station_info)
                    found_station = True
                    break
            
            if not found_station:
                # If station not found, use code as name
                station_info = station.copy()
                station_info['name'] = station['code'] + " (Unknown)"
                station_details.append(station_info)
        
        return render_template('train_schedule.html', train=train, stations=station_details)
    
    return render_template('train_schedule.html')

@app.route('/ticket_booking', methods=['GET', 'POST'])
@login_required
def ticket_booking():
    # For GET requests, render the ticket booking form
    today = datetime.now().strftime('%Y-%m-%d')
    max_date = (datetime.now() + timedelta(days=120)).strftime('%Y-%m-%d')
    return render_template('ticket_booking.html', today=today, max_date=max_date)

@app.route('/book_ticket', methods=['POST'])
@login_required
def book_ticket():
    train_number = request.form.get('train_number')
    from_station = request.form.get('from_station')
    to_station = request.form.get('to_station')
    date = request.form.get('date')
    passenger_name = request.form.get('passenger_name')
    passenger_age = request.form.get('passenger_age')
    passenger_gender = request.form.get('passenger_gender')
    seats = int(request.form.get('seats', 1))
    train_class = request.form.get('class')
    
    if not all([train_number, from_station, to_station, date, passenger_name, 
                passenger_age, passenger_gender, seats, train_class]):
        flash('Please fill all fields', 'error')
        return redirect(url_for('ticket_booking'))
    
    # Generate PNR
    pnr = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    
    # Get train details
    train = find_one('trains', {"number": train_number})
    
    # Get station names
    stations = get_json_data('stations')
    from_station_name = next((station['name'] for station in stations if station['code'] == from_station), from_station)
    to_station_name = next((station['name'] for station in stations if station['code'] == to_station), to_station)
    
    # Create booking with additional info for PDF
    booking = {
        "pnr": pnr,
        "train_number": train_number,
        "train_name": train['name'] if train else "Unknown Train",
        "from_station": from_station,
        "from_station_name": from_station_name,
        "to_station": to_station,
        "to_station_name": to_station_name,
        "date": date,
        "passenger_name": passenger_name,
        "passenger_age": int(passenger_age),
        "passenger_gender": passenger_gender,
        "seats": seats,
        "class": train_class,
        "booking_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "username": session.get('username', 'Guest')
    }
    
    # Store the booking ID in the session so we can access it for PDF generation
    booking_id = insert_one('bookings', booking)
    session['last_booking_pnr'] = pnr
    
    flash(f'Ticket booked successfully! Your PNR is: {pnr}', 'success')
    return redirect(url_for('view_ticket', pnr=pnr))

@app.route('/view_ticket/<pnr>')
@login_required
def view_ticket(pnr):
    # Find the booking by PNR
    booking = find_one('bookings', {"pnr": pnr})
    
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('index'))
    
    # Get train details
    train = find_one('trains', {"number": booking['train_number']})
    
    return render_template('ticket.html', booking=booking, train=train)

@app.route('/download_ticket/<pnr>')
@login_required
def download_ticket(pnr):
    # Find the booking by PNR
    booking = find_one('bookings', {"pnr": pnr})
    
    if not booking:
        flash('Booking not found', 'error')
    return redirect(url_for('index'))
    
    # Get train details
    train = find_one('trains', {"number": booking['train_number']})
    
    if PDF_AVAILABLE:
        # Generate PDF using WeasyPrint if available
        html = render_template('ticket_pdf.html', booking=booking, train=train)
        return render_pdf(HTML(string=html), download_filename=f"ticket_{pnr}.pdf")
    else:
        # Alternative: Just render the PDF template as a regular HTML page
        # This will allow users to print/save as PDF using browser functionality
        html = render_template('ticket_pdf.html', booking=booking, train=train)
        return html

@app.route('/my_bookings')
@login_required
def my_bookings():
    username = session.get('username')
    
    if not username:
        flash('Please login to view your bookings', 'error')
        return redirect(url_for('login'))
    
    # Find all bookings for the logged-in user
    bookings = find('bookings', {"username": username})
    
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/help')
def help():
    return render_template('help.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter username and password', 'error')
            return render_template('login.html')
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Check if user exists
        user = find_one('users', {"username": username})
        
        if not user or user['password'] != hashed_password:
            flash('Invalid username or password', 'error')
            return render_template('login.html')
        
        # Store user info in session
        session['username'] = username
        session['user_id'] = str(user['_id'])
        
        flash('Login successful', 'success')
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([username, email, password, confirm_password]):
            flash('Please fill all fields', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        # Check if username already exists
        existing_user = find_one('users', {"username": username})
        if existing_user:
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        # Check if email already exists
        existing_email = find_one('users', {"email": email})
        if existing_email:
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Create user
        new_user = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        insert_one('users', new_user)
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/search_trains', methods=['GET', 'POST'])
def search_trains():
    # Get all stations for the dropdown
    all_stations = get_json_data('stations')
    
    if request.method == 'POST':
        source = request.form.get('source', '').strip()
        destination = request.form.get('destination', '').strip()
        
        if not source or not destination:
            flash('Please select both source and destination stations', 'error')
            return render_template('search_trains.html', stations=all_stations, now=datetime.now())
        
        if source == destination:
            flash('Source and destination stations cannot be the same', 'error')
            return render_template('search_trains.html', stations=all_stations, now=datetime.now())
        
        # Get all trains
        all_trains = get_json_data('trains')
        matching_trains = []
        
        # Filter trains based on source and destination
        for train in all_trains:
            station_codes = [station['code'] for station in train['stations']]
            
            if source in station_codes and destination in station_codes:
                source_index = station_codes.index(source)
                dest_index = station_codes.index(destination)
                
                # Check if destination comes after source in route
                if source_index < dest_index:
                    # Add source and destination station names
                    for station_doc in all_stations:
                        if station_doc['code'] == source:
                            train['source_name'] = station_doc['name']
                        if station_doc['code'] == destination:
                            train['destination_name'] = station_doc['name']
                    
                    # Add journey details
                    train['journey_source'] = source
                    train['journey_destination'] = destination
                    
                    # Calculate journey time and distance
                    source_station = next((s for s in train['stations'] if s['code'] == source), None)
                    dest_station = next((s for s in train['stations'] if s['code'] == destination), None)
                    
                    if source_station and dest_station:
                        train['journey_distance'] = dest_station['distance'] - source_station['distance']
                        
                        # Calculate time difference if both arrival and departure exist
                        if source_station['departure'] and dest_station['arrival']:
                            source_time = datetime.strptime(source_station['departure'], '%H:%M')
                            dest_time = datetime.strptime(dest_station['arrival'], '%H:%M')
                            
                            # Adjust for overnight journeys
                            day_diff = dest_station['day'] - source_station['day']
                            if day_diff > 0:
                                hours_diff = (dest_time.hour + (day_diff * 24)) - source_time.hour
                                minutes_diff = dest_time.minute - source_time.minute
                                if minutes_diff < 0:
                                    hours_diff -= 1
                                    minutes_diff += 60
                                train['journey_time'] = f"{hours_diff}h {minutes_diff}m"
                            else:
                                time_diff = dest_time - source_time
                                hours = time_diff.seconds // 3600
                                minutes = (time_diff.seconds % 3600) // 60
                                train['journey_time'] = f"{hours}h {minutes}m"
                    
                    matching_trains.append(train)
        
        if not matching_trains:
            flash('No trains found for this route. Try different stations.', 'error')
        
        return render_template('search_trains.html', 
                              stations=all_stations, 
                              source=source, 
                              destination=destination,
                              trains=matching_trains,
                              now=datetime.now())
    
    return render_template('search_trains.html', stations=all_stations, now=datetime.now())

# Add a route to display all available trains
@app.route('/all_trains')
def all_trains():
    trains = get_json_data('trains')
    all_stations = get_json_data('stations')
    
    # Add station names to each train
    for train in trains:
        for station_doc in all_stations:
            if station_doc['code'] == train['source_code']:
                train['source_name'] = station_doc['name']
            if station_doc['code'] == train['destination_code']:
                train['destination_name'] = station_doc['name']
    
    return render_template('all_trains.html', trains=trains)

# Add a route for direct booking without checking seat availability
@app.route('/direct_book', methods=['POST'])
@login_required
def direct_book():
    train_number = request.form.get('train_number')
    from_station = request.form.get('from_station', '').upper()
    to_station = request.form.get('to_station', '').upper()
    train_class = request.form.get('train_class')
    date = request.form.get('travel_date')
    passenger_name = request.form.get('passenger_name')
    passenger_age = request.form.get('passenger_age')
    passenger_gender = request.form.get('passenger_gender')
    seats = int(request.form.get('seats', 1))
    
    # Get payment information
    payment_method = request.form.get('payment_method')
    fare_amount = request.form.get('fare_amount')
    
    if not all([train_number, from_station, to_station, train_class, date, 
                passenger_name, passenger_age, passenger_gender, payment_method]):
        flash('Please fill all required fields', 'error')
        return redirect(url_for('ticket_booking'))
    
    # Find station codes
    from_station_doc = find_one('stations', {"$or": [{"code": from_station}, {"name": from_station}]})
    to_station_doc = find_one('stations', {"$or": [{"code": to_station}, {"name": to_station}]})
    
    if not from_station_doc or not to_station_doc:
        flash('Invalid station names or codes', 'error')
        return redirect(url_for('ticket_booking'))
    
    from_code = from_station_doc['code']
    to_code = to_station_doc['code']
    
    # Find train
    train = find_one('trains', {"number": train_number})
    
    if not train:
        flash('Train not found', 'error')
        return redirect(url_for('ticket_booking'))
    
    # Basic validation
    # Check if train goes from source to destination
    stations_list = [s['code'] for s in train['stations']]
    if from_code not in stations_list or to_code not in stations_list:
        flash('Train does not run between these stations', 'error')
        return redirect(url_for('ticket_booking'))
    
    from_idx = stations_list.index(from_code)
    to_idx = stations_list.index(to_code)
    if from_idx >= to_idx:
        flash('Train does not run from source to destination in this direction', 'error')
        return redirect(url_for('ticket_booking'))
    
    # Check if train runs on the selected day
    booking_date = datetime.strptime(date, '%Y-%m-%d')
    day_name = booking_date.strftime('%a')
    
    if day_name not in train['days']:
        flash('Train does not run on this day', 'error')
        return redirect(url_for('ticket_booking'))
    
    # Check if the selected class is available on this train
    if train_class not in train.get('classes', []) and train_class not in train.get('seats', {}):
        flash(f'Selected class {train_class} is not available on this train', 'error')
        return redirect(url_for('ticket_booking'))
    
    # Process payment
    payment_success, transaction_id = process_payment(payment_method, fare_amount, request.form)
    
    if not payment_success:
        flash('Payment failed. Please try again.', 'error')
        return redirect(url_for('ticket_booking'))
    
    # Generate PNR
    pnr = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    
    # Create booking with additional info for PDF
    booking = {
        "pnr": pnr,
        "train_number": train_number,
        "train_name": train['name'],
        "from_station": from_code,
        "from_station_name": from_station_doc['name'],
        "to_station": to_code,
        "to_station_name": to_station_doc['name'],
        "date": date,
        "passenger_name": passenger_name,
        "passenger_age": int(passenger_age),
        "passenger_gender": passenger_gender,
        "seats": seats,
        "class": train_class,
        "fare_amount": fare_amount,
        "payment_method": payment_method,
        "transaction_id": transaction_id,
        "booking_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "username": session.get('username', 'Guest')
    }
    
    # Store the booking
    booking_id = insert_one('bookings', booking)
    session['last_booking_pnr'] = pnr
    
    flash(f'Payment successful! Ticket booked with PNR: {pnr}', 'success')
    return redirect(url_for('view_ticket', pnr=pnr))

def process_payment(payment_method, amount, form_data):
    """Process payment and return success status and transaction ID"""
    try:
        # This is a simulation of payment processing
        # In a real app, you would integrate with payment gateways
        
        # Validate payment details based on method
        if payment_method == 'credit_card' or payment_method == 'debit_card':
            card_number = form_data.get('card_number', '').replace(' ', '')
            card_name = form_data.get('card_name')
            card_expiry = form_data.get('card_expiry')
            card_cvv = form_data.get('card_cvv')
            
            if not all([card_number, card_name, card_expiry, card_cvv]):
                return False, None
                
            # Simple validation
            if len(card_number) < 15 or not card_number.isdigit():
                return False, None
                
        elif payment_method == 'upi':
            upi_id = form_data.get('upi_id')
            if not upi_id or '@' not in upi_id:
                return False, None
                
        elif payment_method == 'net_banking':
            bank_name = form_data.get('bank_name')
            if not bank_name:
                return False, None
        
        # Generate a random transaction ID
        transaction_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
        
        # For simulation, let's consider the payment as successful
        return True, transaction_id
        
    except Exception as e:
        print(f"Payment processing error: {e}")
        return False, None

@app.route('/transaction_history')
@login_required
def transaction_history():
    username = session.get('username')
    if not username:
        flash('Please login to view your transaction history', 'error')
        return redirect(url_for('login'))
    bookings = find('bookings', {"username": username})
    # Sort by booking date, latest first
    bookings = sorted(bookings, key=lambda b: b.get('booking_date', ''), reverse=True)
    return render_template('transaction_history.html', bookings=bookings)

if __name__ == '__main__':
    init_db()
    app.run(debug=True) 