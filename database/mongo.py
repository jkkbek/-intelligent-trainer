import os
import certifi
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "")

client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
)

db = client["Intelligent_Trainer"]

users_collection = db["users"]
workout_logs_collection = db["workout_logs"]
saved_recommendations_collection = db["saved_recommendations"]
feedback_collection = db["feedback"]
favorites_collection = db["favorites"]
weekly_plans_collection = db["weekly_plans"]