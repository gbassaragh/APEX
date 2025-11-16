"""
Main API router aggregating all v1 endpoints.
"""
from fastapi import APIRouter

from apex.api.v1 import documents, estimates, health, jobs, projects

api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(estimates.router, prefix="/estimates", tags=["estimates"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
