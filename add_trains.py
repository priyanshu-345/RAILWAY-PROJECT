from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['railway_db']

# Collections
stations = db['stations']
trains = db['trains']

# Additional stations
additional_stations = [
    {"code": "LKO", "name": "Lucknow"},
    {"code": "PNBE", "name": "Patna"},
    {"code": "CNB", "name": "Kanpur"},
    {"code": "ALD", "name": "Allahabad"},
    {"code": "GKP", "name": "Gorakhpur"},
    {"code": "VSKP", "name": "Visakhapatnam"},
    {"code": "BPL", "name": "Bhopal"},
    {"code": "JHS", "name": "Jhansi"},
    {"code": "RNC", "name": "Ranchi"},
    {"code": "BBS", "name": "Bhubaneswar"},
    {"code": "NDLS", "name": "New Delhi"},
    {"code": "HWH", "name": "Howrah"}
]

# Additional trains
additional_trains = [
    {
        "number": "12301",
        "name": "Rajdhani Express",
        "source": "NDLS",
        "destination": "PNBE",
        "days": ["Mon", "Wed", "Fri", "Sun"],
        "classes": ["1A", "2A", "3A"],
        "speed": "130",
        "stations": [
            {"code": "NDLS", "arrival": "", "departure": "16:25", "day": 1, "distance": 0},
            {"code": "CNB", "arrival": "21:30", "departure": "21:35", "day": 1, "distance": 440},
            {"code": "ALD", "arrival": "01:15", "departure": "01:20", "day": 2, "distance": 634},
            {"code": "PNBE", "arrival": "06:15", "departure": "", "day": 2, "distance": 1000}
        ],
        "seats": {
            "1A": 20,
            "2A": 50,
            "3A": 100
        }
    },
    {
        "number": "12302",
        "name": "Shatabdi Express",
        "source": "NDLS",
        "destination": "BPL",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "classes": ["CC", "EC"],
        "speed": "130",
        "stations": [
            {"code": "NDLS", "arrival": "", "departure": "06:00", "day": 1, "distance": 0},
            {"code": "JHS", "arrival": "10:30", "departure": "10:32", "day": 1, "distance": 403},
            {"code": "BPL", "arrival": "13:30", "departure": "", "day": 1, "distance": 701}
        ],
        "seats": {
            "CC": 100,
            "EC": 50
        }
    },
    {
        "number": "12303",
        "name": "Duronto Express",
        "source": "NDLS",
        "destination": "LKO",
        "days": ["Mon", "Wed", "Fri", "Sun"],
        "classes": ["1A", "2A", "3A", "SL"],
        "speed": "120",
        "stations": [
            {"code": "NDLS", "arrival": "", "departure": "22:00", "day": 1, "distance": 0},
            {"code": "CNB", "arrival": "02:30", "departure": "02:32", "day": 2, "distance": 440},
            {"code": "LKO", "arrival": "06:00", "departure": "", "day": 2, "distance": 512}
        ],
        "seats": {
            "1A": 15,
            "2A": 40,
            "3A": 80,
            "SL": 150
        }
    },
    {
        "number": "12304",
        "name": "Garib Rath Express",
        "source": "NDLS",
        "destination": "GKP",
        "days": ["Tue", "Thu", "Sat"],
        "classes": ["3A", "SL"],
        "speed": "130",
        "stations": [
            {"code": "NDLS", "arrival": "", "departure": "21:30", "day": 1, "distance": 0},
            {"code": "CNB", "arrival": "02:00", "departure": "02:02", "day": 2, "distance": 440},
            {"code": "LKO", "arrival": "05:30", "departure": "05:32", "day": 2, "distance": 512},
            {"code": "GKP", "arrival": "08:00", "departure": "", "day": 2, "distance": 750}
        ],
        "seats": {
            "3A": 150,
            "SL": 200
        }
    },
    {
        "number": "12305",
        "name": "Coromandel Express",
        "source": "HWH",
        "destination": "VSKP",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "classes": ["1A", "2A", "3A", "SL"],
        "speed": "110",
        "stations": [
            {"code": "HWH", "arrival": "", "departure": "20:00", "day": 1, "distance": 0},
            {"code": "BBS", "arrival": "02:30", "departure": "02:32", "day": 2, "distance": 440},
            {"code": "VSKP", "arrival": "06:00", "departure": "", "day": 2, "distance": 589}
        ],
        "seats": {
            "1A": 20,
            "2A": 50,
            "3A": 100,
            "SL": 150
        }
    },
    {
        "number": "12306",
        "name": "Sampark Kranti Express",
        "source": "NDLS",
        "destination": "RNC",
        "days": ["Mon", "Wed", "Fri", "Sun"],
        "classes": ["2A", "3A", "SL"],
        "speed": "120",
        "stations": [
            {"code": "NDLS", "arrival": "", "departure": "17:30", "day": 1, "distance": 0},
            {"code": "CNB", "arrival": "22:00", "departure": "22:05", "day": 1, "distance": 440},
            {"code": "ALD", "arrival": "02:00", "departure": "02:05", "day": 2, "distance": 634},
            {"code": "RNC", "arrival": "08:00", "departure": "", "day": 2, "distance": 1200}
        ],
        "seats": {
            "2A": 40,
            "3A": 80,
            "SL": 200
        }
    },
    {
        "number": "12307",
        "name": "Vande Bharat Express",
        "source": "NDLS",
        "destination": "VSKP",
        "days": ["Mon", "Wed", "Fri", "Sun"],
        "classes": ["CC", "EC"],
        "speed": "160",
        "stations": [
            {"code": "NDLS", "arrival": "", "departure": "06:00", "day": 1, "distance": 0},
            {"code": "CNB", "arrival": "09:30", "departure": "09:32", "day": 1, "distance": 440},
            {"code": "ALD", "arrival": "12:30", "departure": "12:32", "day": 1, "distance": 634},
            {"code": "VSKP", "arrival": "18:00", "departure": "", "day": 1, "distance": 1200}
        ],
        "seats": {
            "CC": 100,
            "EC": 50
        }
    }
]

def add_data():
    # Add new stations
    for station in additional_stations:
        if not stations.find_one({"code": station["code"]}):
            stations.insert_one(station)
            print(f"Added station: {station['name']} ({station['code']})")

    # Add new trains
    for train in additional_trains:
        if not trains.find_one({"number": train["number"]}):
            trains.insert_one(train)
            print(f"Added train: {train['name']} ({train['number']})")

if __name__ == "__main__":
    add_data()
    print("\nDatabase update completed!") 