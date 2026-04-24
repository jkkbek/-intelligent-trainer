from pymongo import MongoClient
import certifi

MONGO_URI = "mongodb+srv://jksbkaibek_db_user:gQlka13bX6k1jmn2@cluster0.i2pq5pr.mongodb.net/?appName=Cluster0 "

client = MongoClient(MONGO_URI)

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