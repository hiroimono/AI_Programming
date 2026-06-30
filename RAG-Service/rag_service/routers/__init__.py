"""HTTP routers for rag-service.

Exposes the routers under stable names so main.py can include them
without knowing internal module paths.
"""

from rag_service.routers.documents import router as documents_router
from rag_service.routers.retrieve import router as retrieve_router

__all__ = ["documents_router", "retrieve_router"]
