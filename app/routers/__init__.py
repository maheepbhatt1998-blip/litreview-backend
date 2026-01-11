from app.routers.auth import router as auth_router
from app.routers.projects import router as projects_router
from app.routers.papers import router as papers_router
from app.routers.analysis import router as analysis_router

__all__ = ["auth_router", "projects_router", "papers_router", "analysis_router"]
