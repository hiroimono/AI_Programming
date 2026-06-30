"""Re-export Base + all models so Alembic autogenerate sees every table.

Alembic's env.py imports `target_metadata = Base.metadata`; the metadata only
knows about a table if its model class has been *imported* somewhere. We
centralize those imports here so adding a new model is a one-line change.
"""

from rag_service.models.base import Base
from rag_service.models.level2 import Level2Chunk, Level2Document
from rag_service.models.level3 import Level3Chunk, Level3Document

__all__ = [
    "Base",
    "Level2Document",
    "Level2Chunk",
    "Level3Document",
    "Level3Chunk",
]
