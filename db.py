import os
import re
import logging
from datetime import datetime
import json

import mysql.connector
from pymongo import MongoClient
from bson.json_util import dumps

# -------------------------------------------------
# COMMON
# -------------------------------------------------
SERVICE_NAME = os.getenv("SERVICE_NAME", "external-connect")
SERVICE_SAFE = re.sub(r"[^a-zA-Z0-9_]", "_", SERVICE_NAME)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE_NAME)

# -------------------------------------------------
# MYSQL CONFIG
# -------------------------------------------------
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")

MYSQL_DB_NAME = f"{SERVICE_SAFE}_db"

# -------------------------------------------------
# MONGO CONFIG
# -------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = SERVICE_SAFE
MONGO_COLLECTION_NAME = "audit_logs"

# -------------------------------------------------
# MYSQL
# -------------------------------------------------
def ensure_mysql():
    logger.info("Initializing MySQL")

    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB_NAME}`")
    conn.commit()
    cur.close()
    conn.close()

    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=MYSQL_DB_NAME
    )
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS service_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            service VARCHAR(64),
            status VARCHAR(20),
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

    logger.info("MySQL ready")

def insert_mysql_log(status, message):
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=MYSQL_DB_NAME
    )
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO service_logs (service, status, message) VALUES (%s, %s, %s)",
        (SERVICE_NAME, status, message)
    )
    conn.commit()
    cur.close()
    conn.close()

def fetch_mysql_logs(limit=100):
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=MYSQL_DB_NAME
    )
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT id, service, status, message, created_at "
        "FROM service_logs ORDER BY created_at DESC LIMIT %s",
        (limit,)
    )
    rows = cur.fetchall()
    columns = cur.column_names
    cur.close()
    conn.close()

    return {
        "columns": columns,
        "rows": rows
    }

# -------------------------------------------------
# MONGO (EXPLICIT DB + COLLECTION CREATION)
# -------------------------------------------------
_mongo_client = None
_mongo_db = None
_mongo_collection = None

def ensure_mongo():
    global _mongo_client, _mongo_db, _mongo_collection

    logger.info("Initializing MongoDB")

    _mongo_client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000
    )

    # Verify connection + auth
    _mongo_client.admin.command("ping")

    # Step 1: Select database (creates logical DB)
    _mongo_db = _mongo_client[MONGO_DB_NAME]

    # Step 2: Create collection explicitly if missing
    if MONGO_COLLECTION_NAME not in _mongo_db.list_collection_names():
        _mongo_db.create_collection(MONGO_COLLECTION_NAME)
        logger.info("Mongo collection created")

    _mongo_collection = _mongo_db[MONGO_COLLECTION_NAME]

    logger.info(
        f"Mongo ready (db={MONGO_DB_NAME}, collection={MONGO_COLLECTION_NAME})"
    )


def insert_mongo_log(endpoint, method, status, message, details=None):
    if _mongo_collection is None:
        logger.error("Mongo not initialized")
        return

    _mongo_collection.insert_one({
        "service": SERVICE_NAME,
        "endpoint": endpoint,
        "method": method,
        "status": status,
        "message": message,
        "details": details or {},
        "timestamp": datetime.utcnow()
    })


def fetch_mongo_logs(limit=100):
    if _mongo_collection is None:
        return []

    cursor = (
        _mongo_collection
        .find({}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )

    return json.loads(dumps(list(cursor)))
