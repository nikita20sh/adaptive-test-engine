"""
main.py - FastAPI Application Entry Point
Serves the frontend UI at / and all API routes under /api/v1
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import connect_db, close_db
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    connect_db()
    yield
    close_db()


app = FastAPI(
    title="AI-Driven Adaptive Diagnostic Engine",
    description="Adaptive GRE-style test with AI study plan generation.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ── Serve static files (frontend UI) ──
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── API routes ──
app.include_router(router, prefix="/api/v1")


# ── Serve index.html at root ──
@app.get("/", include_in_schema=False)
def serve_ui() -> FileResponse:
    return FileResponse("static/index.html")
