import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Берем DATABASE_URL из переменных окружения Render, либо оставляем SQLite для локалки
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tracker.db")

# Преобразуем формат схемы, если нужно для SQLAlchemy + psycopg2
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://") and not SQLALCHEMY_DATABASE_URL.startswith("postgresql+"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Для SQLite нужен check_same_thread, для PostgreSQL — обычный движок
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Функция зависимости для получения сессии базы данных в FastAPI роутах
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()