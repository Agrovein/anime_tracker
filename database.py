import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Берем DATABASE_URL из переменных окружения Render, либо оставляем SQLite для локалки
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tracker.db")

# PostgreSQL иногда возвращает схему postgres://, которую SQLAlchemy просит заменить на postgresql://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Для SQLite нужен check_same_thread, для PostgreSQL — обычный движок
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()