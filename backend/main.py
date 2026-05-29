from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import create_tables
from routers import search, inventory, identify, import_export, dashboard, config as config_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup
    create_tables()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    print("✓ Database tables ready")
    print("✓ Upload directory ready")
    yield
    # Shutdown (nothing to clean up)


app = FastAPI(
    title="ResellResearch API",
    description="Localhost tool for researching Barbie and board game resell values",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(inventory.router)
app.include_router(identify.router)
app.include_router(import_export.router)
app.include_router(dashboard.router)
app.include_router(config_router.router)


@app.get("/api/health")
async def health():
    from sqlalchemy import text
    from database import SessionLocal
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "db": db_status,
        "ebay_configured": bool(settings.ebay_app_id),
        "etsy_configured": bool(settings.etsy_api_key),
    }
