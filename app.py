from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
import requests
import os
import logging

from db import (
    ensure_mysql,
    ensure_mongo,
    insert_mysql_log,
    fetch_mysql_logs,
    insert_mongo_log,
    fetch_mongo_logs
)

SERVICE = os.getenv("SERVICE_NAME", "external-connect")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE)

app = FastAPI(title=SERVICE)

# -------------------------------------------------
# STARTUP
# -------------------------------------------------
@app.on_event("startup")
def startup():
    ensure_mysql()
    try:
        ensure_mongo()
    except Exception as e:
        # Mongo failure must NOT crash the service
        logger.error(f"Mongo init failed: {e}")

# -------------------------------------------------
# HEALTH
# -------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE}

# -------------------------------------------------
# HTTP
# -------------------------------------------------
session = requests.Session()


PRIVATE_SERVICES = {
    "ai-analysis-plan": "http://ai-analysis-plan.knit-ns.svc.cluster.local/health",
    "ai-ask-knit-service": "http://ai-ask-knit-service.knit-ns.svc.cluster.local/health"
}


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse("frontend/index.html")

@app.post("/success")
def success():
    insert_mysql_log("SUCCESS", "Success action triggered")
    return {"ok": True}

@app.post("/error")
def error():
    insert_mysql_log("ERROR", "Error action triggered")
    return {"ok": True}

@app.get("/check-private-services")
def check_private_services(request: Request):
    results = {}

    for name, url in PRIVATE_SERVICES.items():
        try:
            r = session.get(url, timeout=3)

            insert_mongo_log(
                request.url.path,
                request.method,
                "SUCCESS" if r.ok else "ERROR",
                f"Checked private service {name}",
                {
                    "checked_service": name,
                    "url": url,
                    "http_status": r.status_code
                }
            )
            results[name] = r.status_code

        except Exception as e:
            insert_mongo_log(
                request.url.path,
                request.method,
                "FAIL",
                f"{name} unreachable",
                {"error": str(e)}
            )
            results[name] = "FAIL"

    return results

@app.get("/mysql-logs")
def mysql_logs():
    return fetch_mysql_logs()

@app.get("/mongo-logs")
def mongo_logs():
    try:
        return fetch_mongo_logs()
    except Exception as e:
        logger.error(f"Mongo logs error: {e}")
        return {"error": str(e)}
