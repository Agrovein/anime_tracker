from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Media Tracker")

# Подключаем статику
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    return FileResponse("static/index.html")


# ==================== АВТОРИЗАЦИЯ ====================

@app.post("/api/register")
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
    
    new_user = models.User(username=user_data.username, hashed_password=user_data.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"user_id": new_user.id, "username": new_user.username}

@app.post("/api/login")
def login(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.username == user_data.username,
        models.User.hashed_password == user_data.password
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    return {"user_id": user.id, "username": user.username}


# ==================== КОЛЛЕКЦИИ (СПИСКИ) ====================

# 1. Получить публичные списки (СТРОГО ВЫШЕ динамического роута)
@app.get("/api/collections/public")
def get_public_collections(user_id: Optional[int] = None, db: Session = Depends(get_db)):
    cols = db.query(models.MediaCollection).filter(models.MediaCollection.is_public == True).all()
    res = []
    for c in cols:
        likes_count = len(c.likes)
        is_liked = False
        if user_id:
            is_liked = any(like.user_id == user_id for like in c.likes)
            
        res.append({
            "id": c.id,
            "title": c.title,
            "user_id": c.user_id,
            "is_public": True,
            "owner_username": c.owner.username if c.owner else "Аноним",
            "likes_count": likes_count,
            "is_liked": is_liked
        })
    return res

#Переключение лайка (Лайк / Дизлайк)
@app.post("/api/collections/{collection_id}/like")
def toggle_collection_like(collection_id: int, user_id: int, db: Session = Depends(get_db)):
    col = db.query(models.MediaCollection).filter(models.MediaCollection.id == collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Список не найден")
    
    existing_like = db.query(models.CollectionLike).filter(
        models.CollectionLike.collection_id == collection_id,
        models.CollectionLike.user_id == user_id
    ).first()

    if existing_like:
        db.delete(existing_like)
        db.commit()
        return {"liked": False, "likes_count": len(col.likes)}
    else:
        new_like = models.CollectionLike(collection_id=collection_id, user_id=user_id)
        db.add(new_like)
        db.commit()
        return {"liked": True, "likes_count": len(col.likes)}

#Клонирование (Дублирование) списка
@app.post("/api/collections/{collection_id}/clone")
def clone_collection(collection_id: int, clone_data: schemas.CollectionClone, db: Session = Depends(get_db)):
    source_col = db.query(models.MediaCollection).filter(models.MediaCollection.id == collection_id).first()
    if not source_col:
        raise HTTPException(status_code=404, detail="Исходный список не найден")

    # Создаем новый список под тем же именем (без суффикса "копия")
    new_col = models.MediaCollection(
        title=source_col.title,
        user_id=clone_data.user_id,
        is_public=False
    )
    db.add(new_col)
    db.flush()

    mode = clone_data.mode  # 'full', 'titles_with_meta', 'titles_only'

    for t in source_col.titles:
        new_title = models.MediaTitle(
            collection_id=new_col.id,
            title=t.title,
            release_day=t.release_day,
            comment=t.comment if mode != 'titles_only' else None,
            rating=t.rating if mode != 'titles_only' else None
        )
        db.add(new_title)
        db.flush()

        # Копируем теги тайтла через связь TitleTag
        if mode != 'titles_only' and hasattr(t, 'tags') and t.tags:
            for tag in t.tags:
                tag_name = tag.name if hasattr(tag, 'name') else str(tag)
                db.add(models.TitleTag(media_title_id=new_title.id, name=tag_name))

        if mode == 'full':
            for s in t.seasons:
                new_season = models.Season(
                    media_title_id=new_title.id,
                    title=s.title,
                    default_duration_mins=s.default_duration_mins,
                    comment=s.comment,
                    rating=s.rating,
                    order_index=s.order_index
                )
                db.add(new_season)
                db.flush()

                # Копируем теги сезона
                if hasattr(s, 'tags') and s.tags:
                    for tag in s.tags:
                        tag_name = tag.name if hasattr(tag, 'name') else str(tag)
                        db.add(models.SeasonTag(season_id=new_season.id, name=tag_name))

                for u in s.units:
                    # ИСПРАВЛЕНО: используем models.MediaUnit вместо models.Unit
                    new_unit = models.MediaUnit(
                        season_id=new_season.id,
                        display_number=u.display_number,
                        title=u.title,
                        unit_type=u.unit_type,
                        duration_mins=u.duration_mins,
                        order_index=u.order_index,
                        is_watched=getattr(u, 'is_watched', False),
                        rating=u.rating,
                        comment=u.comment
                    )
                    db.add(new_unit)

    db.commit()
    return {"message": "Список успешно скопирован", "new_collection_id": new_col.id}

# 2. Получить списки конкретного пользователя
@app.get("/api/collections/{user_id}")
def get_user_collections(user_id: int, db: Session = Depends(get_db)):
    cols = db.query(models.MediaCollection).filter(models.MediaCollection.user_id == user_id).all()
    res = []
    for c in cols:
        res.append({
            "id": c.id,
            "title": c.title,
            "user_id": c.user_id,
            "is_public": c.is_public,
            "owner_username": c.owner.username if c.owner else "Я"
        })
    return res

# 3. Создать список
@app.post("/api/collections")
def create_collection(col_data: schemas.CollectionCreate, db: Session = Depends(get_db)):
    new_col = models.MediaCollection(
        title=col_data.title,
        user_id=col_data.user_id,
        is_public=col_data.is_public if col_data.is_public is not None else False
    )
    db.add(new_col)
    db.commit()
    db.refresh(new_col)
    return new_col

# 4. Переключить видимость (Публичный / Приватный)
@app.put("/api/collections/{collection_id}/toggle-public")
def toggle_collection_public(collection_id: int, db: Session = Depends(get_db)):
    col = db.query(models.MediaCollection).filter(models.MediaCollection.id == collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Список не найден")
    
    col.is_public = not col.is_public
    db.commit()
    return {"id": col.id, "is_public": col.is_public}

# 5. Удалить список (с проверкой прав)
@app.delete("/api/collections/{collection_id}")
def delete_collection(collection_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    col = db.query(models.MediaCollection).filter(models.MediaCollection.id == collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Список не найден")
    
    if user_id and col.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя удалить чужой список")
    
    db.delete(col)
    db.commit()
    return {"message": "Список успешно удален"}


# ==================== ТАЙТЛЫ ====================

@app.get("/api/collections/{collection_id}/titles")
def get_titles_by_collection(collection_id: int, db: Session = Depends(get_db)):
    col = db.query(models.MediaCollection).filter(models.MediaCollection.id == collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Список не найден")
    
    titles = col.titles
    titles_data = []
    
    total_episodes = 0
    total_movies = 0
    total_specials = 0
    total_seasons = 0
    total_hours = 0.0

    for t in titles:
        t_episodes = 0
        t_movies = 0
        t_specials = 0
        t_mins = 0
        
        latest_season_title = None
        latest_unit_num = None
        latest_season_tags = []

        for s in t.seasons:
            total_seasons += 1
            latest_season_title = s.title
            # Сохраняем теги текущего сезона (в конце цикла тут останутся теги самого последнего сезона)
            latest_season_tags = [tag.name for tag in s.tags] if hasattr(s, 'tags') else []
            
            for u in s.units:
                latest_unit_num = u.display_number
                dur = u.duration_mins if u.duration_mins else s.default_duration_mins
                t_mins += dur
                if u.unit_type == "movie":
                    t_movies += 1
                    total_movies += 1
                elif u.unit_type == "special":
                    t_specials += 1
                else:
                    t_episodes += 1
                    total_episodes += 1

        t_hours = round(t_mins / 60, 1)
        total_hours += t_mins

        titles_data.append({
            "id": t.id,
            "title": t.title,
            "collection_id": t.collection_id,
            "tags": latest_season_tags,  # <--- Теперь здесь всегда теги из последнего сезона!
            "release_day": t.release_day,
            "comment": t.comment,
            "rating": t.rating,
            "last_edited_at": t.last_edited_at.isoformat() if t.last_edited_at else None,
            "seasons_count": len(t.seasons),
            "total_episodes": t_episodes,
            "total_movies": t_movies,
            "total_hours": t_hours,
            "latest_season_title": latest_season_title,
            "latest_unit_num": latest_unit_num,
            "missed_episodes": 0
        })

    stats = {
        "titles": len(titles),
        "seasons": total_seasons,
        "episodes": total_episodes,
        "movies": total_movies,
        "specials": total_specials,
        "total_hours": round(total_hours / 60, 1)
    }

    return {"titles": titles_data, "stats": stats}

@app.post("/api/titles")
def create_title(title_data: schemas.TitleCreate, db: Session = Depends(get_db)):
    col = db.query(models.MediaCollection).filter(models.MediaCollection.id == title_data.collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Список не найден")
    if col.user_id != title_data.user_id:
        raise HTTPException(status_code=403, detail="Нельзя изменять чужие списки")

    # Создаем тайтл без тегов
    new_title = models.MediaTitle(
        title=title_data.title,
        collection_id=title_data.collection_id,
        release_day=title_data.release_day,
        comment=title_data.comment,
        rating=title_data.rating
    )
    db.add(new_title)
    db.flush() # Получаем ID нового тайтла

    # Создаем теги из прилетевшего массива строк
    if title_data.tags and isinstance(title_data.tags, list):
        for tag_name in title_data.tags:
            if tag_name:
                # В зависимости от того, как у тебя называется поле в модели TitleTag 
                # (обычно name или title), подставь нужное. Пусть будет name:
                new_tag = models.TitleTag(media_title_id=new_title.id, name=tag_name)
                db.add(new_tag)

    db.commit()
    db.refresh(new_title)
    return new_title

@app.put("/api/titles/{title_id}")
def update_title(title_id: int, title_data: schemas.TitleUpdate, user_id: int, db: Session = Depends(get_db)):
    t = db.query(models.MediaTitle).filter(models.MediaTitle.id == title_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Тайтл не найден")
    if t.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя изменять чужие тайтлы")

    # Обновляем только обычные поля тайтла (название, статус и т.д.)
    for key, value in title_data.model_dump(exclude_unset=True, exclude={'tags'}):
        setattr(t, key, value)
    
    db.commit()
    db.refresh(t)
    return t

@app.delete("/api/titles/{title_id}")
def delete_title(title_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    t = db.query(models.MediaTitle).filter(models.MediaTitle.id == title_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Тайтл не найден")
    if user_id and t.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя удалять чужие тайтлы")

    db.delete(t)
    db.commit()
    return {"message": "Тайтл удален"}

@app.get("/api/titles/{title_id}/details")
def get_title_details(title_id: int, db: Session = Depends(get_db)):
    t = db.query(models.MediaTitle).filter(models.MediaTitle.id == title_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Тайтл не найден")
    
    seasons_data = []
    total_episodes = 0
    total_mins = 0
    total_global_units = 0

    for s in t.seasons:
        units_data = []
        for u in s.units:
            total_global_units += 1
            dur = u.duration_mins if u.duration_mins else s.default_duration_mins
            if u.unit_type == "episode":
                total_episodes += 1
            total_mins += dur

            units_data.append({
                "id": u.id,
                "season_id": u.season_id,
                "display_number": u.display_number,
                "global_number": total_global_units,
                "title": u.title,
                "unit_type": u.unit_type,
                "duration_mins": u.duration_mins,
                "rating": u.rating,
                "comment": u.comment
            })

        seasons_data.append({
            "id": s.id,
            "title": s.title,
            "media_title_id": s.media_title_id,
            "default_duration_mins": s.default_duration_mins,
            "tags": s.tags,
            "comment": s.comment,
            "rating": s.rating,
            "order_index": s.order_index,
            "units": units_data
        })

    return {
        "id": t.id,
        "title": t.title,
        "release_day": t.release_day,
        "total_episodes": total_episodes,
        "total_hours": round(total_mins / 60, 1),
        "total_global_units": total_global_units,
        "seasons": seasons_data
    }


# ==================== СЕЗОНЫ ====================

@app.post("/api/seasons")
def create_season(season_data: schemas.SeasonCreate, user_id: int, db: Session = Depends(get_db)):
    title = db.query(models.MediaTitle).filter(models.MediaTitle.id == season_data.media_title_id).first()
    if not title:
        raise HTTPException(status_code=404, detail="Тайтл не найден")
    if title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя добавлять сезоны в чужие тайтлы")

    max_order = db.query(func.max(models.Season.order_index)).filter(models.Season.media_title_id == season_data.media_title_id).scalar() or 0
    
    new_season = models.Season(
        title=season_data.title,
        media_title_id=season_data.media_title_id,
        default_duration_mins=season_data.default_duration_mins,
        comment=season_data.comment,
        rating=season_data.rating,
        order_index=max_order + 1
    )
    db.add(new_season)
    db.flush()

    # Собираем теги из запроса
    tags_to_save = list(season_data.tags) if season_data.tags and isinstance(season_data.tags, list) else []

    # Логика автотегов по длительности (если указана длительность)
    if new_season.default_duration_mins is not None and new_season.default_duration_mins > 0:
        auto_tag = "short(5min)" if new_season.default_duration_mins < 10 else "long(15min)"
        # Удаляем противоположный автотег на всякий случай и добавляем актуальный
        tags_to_save = [t for t in tags_to_save if t not in ("short(5min)", "long(15min)")]
        tags_to_save.append(auto_tag)

    # Сохраняем итоговый список тегов
    for tag_name in tags_to_save:
        if tag_name:
            new_tag = models.SeasonTag(season_id=new_season.id, name=tag_name)
            db.add(new_tag)

    db.commit()
    db.refresh(new_season)
    return new_season

@app.put("/api/seasons/{season_id}")
def update_season(season_id: int, season_data: schemas.SeasonUpdate, user_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Season).filter(models.Season.id == season_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Сезон не найден")
    if s.media_title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя редактировать чужие сезоны")

    update_dict = season_data.model_dump(exclude_unset=True)
    tags_data = update_dict.pop('tags', None)

    for key, value in update_dict.items():
        setattr(s, key, value)
    
    # Безопасно собираем текущие теги
    if tags_data is not None:
        current_tags = [t for t in tags_data if t]
    else:
        current_tags = [t.name for t in s.tags]

    # Пересчитываем автотег длительности
    duration_to_check = s.default_duration_mins
    if duration_to_check is not None and duration_to_check > 0:
        auto_tag = "short(5min)" if duration_to_check < 10 else "long(15min)"
        current_tags = [t for t in current_tags if t not in ("short(5min)", "long(15min)")]
        current_tags.append(auto_tag)

    # Полностью синхронизируем теги в базе
    db.query(models.SeasonTag).filter(models.SeasonTag.season_id == s.id).delete()
    for tag_name in current_tags:
        new_tag = models.SeasonTag(season_id=s.id, name=tag_name)
        db.add(new_tag)
    
    db.commit()
    db.refresh(s)
    return s

@app.delete("/api/seasons/{season_id}")
def delete_season(season_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    s = db.query(models.Season).filter(models.Season.id == season_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Сезон не найден")
    if user_id and s.media_title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя удалять чужие сезоны")

    db.delete(s)
    db.commit()
    return {"message": "Сезон удален"}

@app.post("/api/seasons/{season_id}/move")
def move_season(season_id: int, move_data: schemas.MoveRequest, user_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Season).filter(models.Season.id == season_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Сезон не найден")
    if s.media_title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя перемещать сезоны в чужих тайтлах")

    title_id = s.media_title_id
    seasons = db.query(models.Season).filter(models.Season.media_title_id == title_id).order_by(models.Season.order_index).all()
    
    idx = next((i for i, item in enumerate(seasons) if item.id == season_id), -1)
    if idx == -1:
        raise HTTPException(status_code=400, detail="Ошибка порядка")

    if move_data.direction == "up" and idx > 0:
        seasons[idx].order_index, seasons[idx-1].order_index = seasons[idx-1].order_index, seasons[idx].order_index
    elif move_data.direction == "down" and idx < len(seasons) - 1:
        seasons[idx].order_index, seasons[idx+1].order_index = seasons[idx+1].order_index, seasons[idx].order_index

    db.commit()
    return {"message": "Порядок обновлен"}


# ==================== ЭПИЗОДЫ / ЮНИТЫ ====================

def parse_order_index(display_str: str, fallback_order: float) -> float:
    try:
        # Пытаемся превратить display_number в float (например, "263.5" -> 263.5)
        # Убираем всё лишнее, если вдруг там есть пробелы
        clean_str = str(display_str).strip()
        return float(clean_str)
    except (ValueError, TypeError):
        # Если это не чистое число (например, "OVA"), возвращаем fallback (например, в конец списка)
        return float(fallback_order)

@app.post("/api/units")
def create_unit(unit_data: schemas.UnitCreate, user_id: int, db: Session = Depends(get_db)):
    season = db.query(models.Season).filter(models.Season.id == unit_data.season_id).first()
    if not season:
        raise HTTPException(status_code=404, detail="Сезон не найден")
    if season.media_title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя добавлять серии в чужие сезоны")

    # Вычисляем порядок на основе максимального order_index в сезоне
    max_order = db.query(func.max(models.MediaUnit.order_index)).filter(models.MediaUnit.season_id == unit_data.season_id).scalar() or 0.0
    try:
        calculated_order = float(unit_data.display_number)
    except ValueError:
        calculated_order = max_order + 1.0

    # Создаем словарь данных и принудительно добавляем рассчитанный order_index
    unit_dict = unit_data.model_dump()
    unit_dict["order_index"] = calculated_order

    new_unit = models.MediaUnit(**unit_dict)
    db.add(new_unit)
    db.commit()
    db.refresh(new_unit)
    return new_unit

@app.post("/api/units/batch")
def create_batch_units(batch_data: schemas.BatchUnitCreate, user_id: int, db: Session = Depends(get_db)):
    season = db.query(models.Season).filter(models.Season.id == batch_data.season_id).first()
    if not season:
        raise HTTPException(status_code=404, detail="Сезон не найден")
    if season.media_title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя изменять чужие сезоны")

    max_order = db.query(func.max(models.MediaUnit.order_index)).filter(models.MediaUnit.season_id == batch_data.season_id).scalar() or 0.0

    for i in range(batch_data.start, batch_data.end + 1):
        max_order += 1.0
        new_unit = models.MediaUnit(
            season_id=batch_data.season_id,
            display_number=str(i),
            unit_type="episode",
            duration_mins=season.default_duration_mins,
            order_index=max_order
        )
        db.add(new_unit)
    
    db.commit()
    return {"message": "Пакет серий успешно добавлен"}

@app.put("/api/units/{unit_id}")
def update_unit(unit_id: int, unit_data: schemas.UnitUpdate, user_id: int, db: Session = Depends(get_db)):
    u = db.query(models.MediaUnit).filter(models.MediaUnit.id == unit_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Элемент не найден")
    if u.season.media_title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя изменять чужие серии")

    for key, value in unit_data.model_dump(exclude_unset=True).items():
        setattr(u, key, value)
    
    db.commit()
    db.refresh(u)
    return u

@app.delete("/api/units/{unit_id}")
def delete_unit(unit_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    u = db.query(models.MediaUnit).filter(models.MediaUnit.id == unit_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Элемент не найден")
    if user_id and u.season.media_title.collection.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя удалять чужие серии")

    db.delete(u)
    db.commit()
    return {"message": "Элемент удален"}

@app.put("/api/collections/{collection_id}")
def update_collection(collection_id: int, user_id: int, title: str, db: Session = Depends(get_db)):
    col = db.query(models.MediaCollection).filter(models.MediaCollection.id == collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Список не найден")
    if col.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя изменять чужие списки")
    
    col.title = title.strip()
    db.commit()
    db.refresh(col)
    return col