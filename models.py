from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    collections = relationship("MediaCollection", back_populates="owner", cascade="all, delete-orphan")
    likes = relationship("CollectionLike", back_populates="user", cascade="all, delete-orphan")


class MediaCollection(Base):
    __tablename__ = "media_collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="collections")
    titles = relationship("MediaTitle", back_populates="collection", cascade="all, delete-orphan")
    likes = relationship("CollectionLike", back_populates="collection", cascade="all, delete-orphan")


class MediaTitle(Base):
    __tablename__ = "media_titles"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("media_collections.id"), nullable=False)
    title = Column(String, index=True, nullable=False)
    cover_url = Column(String, nullable=True)
    
    # Статусы и автоматика сортировки
    is_finished = Column(Boolean, default=False)  # Завершен ли тайтл
    release_day = Column(String, nullable=True)     # День недели выхода (например, "Saturday")
    last_edited_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Оценка и комментарий
    rating = Column(Float, nullable=True)
    comment = Column(Text, nullable=True)

    collection = relationship("MediaCollection", back_populates="titles")
    seasons = relationship("Season", back_populates="media_title", cascade="all, delete-orphan", order_by="Season.order_index")
    tags = relationship("TitleTag", back_populates="media_title", cascade="all, delete-orphan")


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    media_title_id = Column(Integer, ForeignKey("media_titles.id"), nullable=False)
    title = Column(String, nullable=False)
    order_index = Column(Float, default=1.0)
    
    default_duration_mins = Column(Integer, default=20)
    is_finished = Column(Boolean, default=False)
    
    rating = Column(Float, nullable=True)
    comment = Column(Text, nullable=True)

    media_title = relationship("MediaTitle", back_populates="seasons")
    units = relationship("MediaUnit", back_populates="season", cascade="all, delete-orphan", order_by="MediaUnit.order_index")
    tags = relationship("SeasonTag", back_populates="season", cascade="all, delete-orphan")


class MediaUnit(Base):
    __tablename__ = "media_units"

    id = Column(Integer, primary_key=True, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    
    title = Column(String, nullable=True)
    display_number = Column(String, nullable=False)  # "1", "12.5", "Фильм"
    unit_type = Column(String, default="episode")    # "episode", "movie", "special"
    duration_mins = Column(Integer, nullable=True)
    order_index = Column(Float, nullable=False)
    
    is_watched = Column(Boolean, default=False)
    rating = Column(Float, nullable=True)
    comment = Column(Text, nullable=True)

    season = relationship("Season", back_populates="units")


class TitleTag(Base):
    __tablename__ = "title_tags"

    id = Column(Integer, primary_key=True, index=True)
    media_title_id = Column(Integer, ForeignKey("media_titles.id"), nullable=False)
    name = Column(String, nullable=False)  # "#2D", "#3D", "#ИИ"

    media_title = relationship("MediaTitle", back_populates="tags")


class SeasonTag(Base):
    __tablename__ = "season_tags"

    id = Column(Integer, primary_key=True, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    name = Column(String, nullable=False)

    season = relationship("Season", back_populates="tags")

class CollectionLike(Base):
    __tablename__ = "collection_likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    collection_id = Column(Integer, ForeignKey("media_collections.id"), nullable=False)

    user = relationship("User", back_populates="likes")
    collection = relationship("MediaCollection", back_populates="likes")