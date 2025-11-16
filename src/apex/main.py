"""
FastAPI application entry point for APEX.

Enterprise estimation platform for utility T&D projects.
"""
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apex.api.v1.router import api_router
from apex.config import config
from apex.models.schemas import ErrorResponse
from apex.utils.errors import BusinessRuleViolation
from apex.utils.logging import setup_logging
from apex.utils.middleware import RequestIDMiddleware

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info(f"Debug mode: {config.DEBUG}")

    yield

    # Shutdown
    logger.info(f"Shutting down {config.APP_NAME}")


# Create FastAPI application
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="AI-Powered Estimation Expert for utility T&D projects",
    docs_url="/docs" if config.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if config.DEBUG else None,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(BusinessRuleViolation)
async def business_rule_handler(request: Request, exc: BusinessRuleViolation):
    """
    Handle business rule violations with standardized error response.

    Args:
        request: FastAPI request
        exc: Business rule violation exception

    Returns:
        JSON response with error details (400)
    """
    request_id = getattr(request.state, "request_id", None)
    payload = ErrorResponse(
        error_code=exc.code or "BUSINESS_RULE_VIOLATION",
        message=str(exc),
        details=exc.details,
        request_id=request_id,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=400, content=payload.model_dump(mode="json"))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions with standardized error response.

    Args:
        request: FastAPI request
        exc: Exception

    Returns:
        JSON response with error details (500)
    """
    request_id = getattr(request.state, "request_id", None)
    logger.error("Unhandled exception: %s", traceback.format_exc())

    # Hide internal details in production
    message = "An unexpected error occurred"
    if config.DEBUG:
        message = str(exc)

    payload = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message=message,
        details=None,
        request_id=request_id,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))


# Include API router
app.include_router(api_router, prefix=config.API_V1_PREFIX)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": config.APP_NAME,
        "version": config.APP_VERSION,
        "status": "operational",
        "docs": f"{config.API_V1_PREFIX}/docs" if config.DEBUG else "disabled",
    }
