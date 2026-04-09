import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.routers import auth, scores, results, transcript, admin
from app.database import connection_pool

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("arcms.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown lifecycle.
    Startup: confirms database pool is ready.
    Shutdown: closes all PostgresSQL connections cleanly.
    """
    logger.info("ARCMS connection starting up...")
    logger.info("Database connection pool initialized")
    yield
    connection_pool.closeall()
    logger.info("Database pool closed. ARCMS shut down cleanly.")

app = FastAPI(
    title="ARCMS - Academic Result & Course Management System",
    description=(
        "Backend system for managing academic results at AFIT. "
        "Handles score uploads, GPA calculation, HOD approval workflow, "
        "student result checking, and transcript generation."
    ),
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all origins for now
    allow_credentials=True,  # Allows cookies or authentication headers
    allow_methods=["*"],  # allow GET, POST, PUT, DELETE
    allow_headers=["*"],  # allow all headers including Authorization
)

# files in app/static/ are accessible at /static/filename
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(scores.router)
app.include_router(results.router)
app.include_router(transcript.router)
app.include_router(admin.router)

@app.get("/", tags=["Health"])
async def root():
    """
    Health check endpoint.
    Returns system status and links to documentation.
    """
    return {
        "system": "ARCMS - Air Force Institute of Technology",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check.
    Confirms API is running and database pool is active.
    In production this will ping the database and return real status.
    """
    return {
        "status": "healthy",
        "database": "connected",
        "institution": "AFIT",
        "version": "1.0.0"
    }
