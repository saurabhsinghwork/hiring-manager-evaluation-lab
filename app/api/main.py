"""Main FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.api.routes.health import router as health_router
from app.api.routes.models import router as models_router
from app.api.routes.workflows import router as workflows_router
from app.api.routes.evaluations import router as evaluations_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    setup_logging()
    logger.info("Starting Hiring Manager Evaluation Lab API service...")
    # Ensure evaluation data directory exists
    settings.evaluation_data_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Evaluation store directory verified at: {settings.evaluation_data_dir}")
    yield
    logger.info("Shutting down Hiring Manager Evaluation Lab API service...")

app = FastAPI(
    title="Hiring Manager Evaluation Lab API",
    version="1.0.0",
    description="Backend REST API for adversarial multi-agent hiring manager evaluations",
    lifespan=lifespan
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all route modules
app.include_router(health_router)
app.include_router(models_router)
app.include_router(workflows_router)
app.include_router(evaluations_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:app", host=settings.api_host, port=settings.api_port, reload=True)
