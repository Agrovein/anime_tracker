import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# По умолчанию на локалке создаем файл tracker.db
# В облаке мы заменим этот URL на адрес Supabase через переменные окружения
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tracker.db")

# Для SQLite нужен специальный аргумент check_same_thread, для Postgres он не нужен
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Функция, которая будет выдавать сессию базы данных для запросов
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()