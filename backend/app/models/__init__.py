"""SQLAlchemy models. Import all model modules here so `Base.metadata`
contains every table before Alembic autogenerate or `create_all` runs.
"""
from app.models.base import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.video import Video  # noqa: F401
from app.models.video_specification import VideoSpecification  # noqa: F401
from app.models.render_job import RenderJob  # noqa: F401
from app.models.asset import Asset  # noqa: F401

__all__ = ["Base", "User", "Video", "VideoSpecification", "RenderJob", "Asset"]
