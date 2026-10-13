from typing import List, Optional
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str

class CollectionCreate(BaseModel):
    title: str
    user_id: int
    is_public: Optional[bool] = False

class CollectionResponse(BaseModel):
    id: int
    title: str
    user_id: int
    is_public: bool
    owner_username: Optional[str] = None

    class Config:
        from_attributes = True

# --- ТАЙТЛЫ ---
class TitleCreate(BaseModel):
    title: str
    collection_id: int
    user_id: int  # <--- Добавили для проверки прав владельца
    tags: Optional[List[str]] = []
    release_day: Optional[str] = None
    comment: Optional[str] = None
    rating: Optional[float] = None

class TitleUpdate(BaseModel):
    title: Optional[str] = None
    user_id: Optional[int] = None  # <--- Добавили для проверки прав владельца
    tags: Optional[List[str]] = None
    release_day: Optional[str] = None
    comment: Optional[str] = None
    rating: Optional[float] = None

# --- СЕЗОНЫ ---
class SeasonCreate(BaseModel):
    title: str
    media_title_id: int
    default_duration_mins: Optional[int] = 20
    tags: Optional[List[str]] = []
    comment: Optional[str] = None
    rating: Optional[float] = None

class SeasonUpdate(BaseModel):
    title: Optional[str] = None
    default_duration_mins: Optional[int] = None
    tags: Optional[List[str]] = None
    comment: Optional[str] = None
    rating: Optional[float] = None

class MoveRequest(BaseModel):
    direction: str

# --- ЭПИЗОДЫ / ЮНИТЫ ---
class UnitCreate(BaseModel):
    season_id: int
    display_number: str
    title: Optional[str] = None
    unit_type: Optional[str] = "episode"
    duration_mins: Optional[int] = None

class BatchUnitCreate(BaseModel):
    season_id: int
    start: int
    end: int

class UnitUpdate(BaseModel):
    title: Optional[str] = None
    unit_type: Optional[str] = None
    duration_mins: Optional[int] = None
    rating: Optional[float] = None
    comment: Optional[str] = None

class CollectionClone(BaseModel):
    user_id: int
    mode: str  # 'full', 'titles_with_meta', 'titles_only'