"""Database models for Videoforce MVP.

Import Base from this package: from apps.api.models import Base
Individual model modules: from apps.api.models.user import User, etc.
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()