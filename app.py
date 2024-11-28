from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from pydantic import ValidationError
import sqlite3
import ipaddress
import re
import os

# Импортируем необходимые модули
from modules.arcsight_api import ArcSightAPI
from modules.kuma_api import KumaRestAPIv2

# Инициализация FastAPI
app = FastAPI()

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="static"), name='static')

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Файл базы данных
DB_FILE = "iocs.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Таблица для IOC
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS iocs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attribute_type TEXT NOT NULL,
            value TEXT NOT NULL,
            description TEXT,
            UNIQUE(attribute_type, value)
        )
        """)
        # Таблица для статусов отправки
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ioc_statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ioc_id INTEGER NOT NULL,
            service_url TEXT NOT NULL,
            status_code INTEGER,
            error_message TEXT,
            FOREIGN KEY(ioc_id) REFERENCES iocs(id)
        )
        """)
        conn.commit()

init_db()

# Определение допустимых типов атрибутов
class AttributeType(str, Enum):
    src_ip = "src-ip"
    dst_ip = "dst-ip"
    src_ip_port = "src-ip|port"
    dst_ip_port = "dst-ip|port"
    filename = "filename"
    md5 = "md5"
    sha1 = "sha1"
    sha256 = "sha256"
    FQDN = "FQDN"
    # Добавьте другие типы по необходимости

# Модель IOC с валидацией
class IOC(BaseModel):
    attribute_type: AttributeType = Field(..., description="The type of IOC attribute")
    value: str = Field(..., description="The value of the attribute")
    description: Optional[str] = Field(None, max_length=255, description="An optional description of the IOC")

    @model_validator(mode='after')
    def validate_ioc(cls, model):
        attribute_type = model.attribute_type
        value = model.value

        if attribute_type in ["src-ip", "dst-ip"]:
            try:
                ipaddress.ip_address(value)
            except ValueError:
                raise ValueError("Invalid IP address format")
        elif attribute_type in ["src-ip|port", "dst-ip|port"]:
            if '|' not in value:
                raise ValueError("Value must be in the format 'IP|Port'")
            ip_part, port_part = value.split('|', 1)
            try:
                ipaddress.ip_address(ip_part)
            except ValueError:
                raise ValueError("Invalid IP address in 'IP|Port'")
            if not port_part.isdigit():
                raise ValueError("Port must be a number")
        elif attribute_type == "FQDN":
            if '.' not in value:
                raise ValueError("Bad FQDN")
        elif attribute_type == "filename":
            if len(value) > 255:
                raise ValueError("Filename must not exceed 255 characters")
            # Дополнительная валидация для имени файла
        elif attribute_type in ["md5", "sha1", "sha256"]:
            hash_patterns = {
                "md5": r'^[a-fA-F0-9]{32}$',
                "sha1": r'^[a-fA-F0-9]{40}$',
                "sha256": r'^[a-fA-F0-9]{64}$',
            }
            pattern = hash_patterns[attribute_type]
            if not re.match(pattern, value):
                raise ValueError(f"Invalid {attribute_type} hash format")
        else:
            raise ValueError(f"Unsupported attribute type: {attribute_type}")
        return model

# Модель для поискового запроса
class SearchQuery(BaseModel):
    attribute_type: Optional[AttributeType] = None
    value: Optional[str] = None

# Список сервисов для отправки IOC
services = [
    {
        "name": "mts_bank",
        "type": "kuma",
        "data": {
            "url": "https://0001kumcore01.msk.mts.ru",
            "token": os.environ.get('KUMA_PAO', None),
            "FQDN": "a4db230f-e2ea-48e4-b8cd-c0b721d21d04",
            "src-ip": "da86140c-0b22-4338-aa24-ba3640b5cf7c"
        }
    },
    {
        "name": "main_core",
        "type": "kuma",
        "data": {
            "url": "https://0400kumcore01.pv.mts.ru",
            "token": os.environ.get('KUMA_MAIN', None),
            "FQDN":"c3677a36-3dd4-440e-b574-1f872f73258b",
            "src-ip":"fb4ff0fa-1c35-4db0-a86f-f6b34857d4e3"
        }
    },
    {
        "name": "arc_sight",
        "type": "arcsight",
        "data": {
            "url": "https://0400arc-esm-mb01.pv.mts.ru",
            "token": os.environ.get('ARC_TOKEN', None),
            "FQDN":"Hvu-5sIwBABDGoBZZHVhMTA%3D%3D",
            "src-ip":"HRh56KosBABD2lRvZadoKag%3D%3D"
        }
    },
    # Добавьте другие сервисы при необходимости
]

@app.get("/")
async def serve_index():
    """Главная страница"""
    return FileResponse("static/index.html")

# Функция для отправки IOC в KUMA
async def send_ioc_to_kuma(data: dict, ioc_id: int, ioc: IOC):
    try:
        kapi = KumaRestAPIv2(data['url'], data['token'])
        dictionary_id = data.get(ioc.attribute_type)
        if not dictionary_id:
            raise Exception(f"Dictionary ID for attribute type '{ioc.attribute_type}' not found in service data.")
        # Предполагаем, что метод возвращает (status, response)
        status, response = kapi.add_dictionary_row(
            dictionary_id,
            ioc.value,
            {"value": ioc.description})
        status_code = status  # Предполагаем успешное выполнение
        error_message = None
    except Exception as e:
        status_code = None
        error_message = str(e)
    # Сохраняем статус в базе данных
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ioc_statuses (ioc_id, service_url, status_code, error_message) VALUES (?, ?, ?, ?)",
            (ioc_id, data['url'], status_code, error_message)
        )
        conn.commit()

# Функция для отправки IOC в ArcSight
async def send_ioc_to_arcsight(data: dict, ioc_id: int, ioc: IOC):
    try:
        aapi = ArcSightAPI(data['url'], data['token'])
        list_id = data.get(ioc.attribute_type)
        if not list_id:
            raise Exception(f"List ID for attribute type '{ioc.attribute_type}' not found in service data.")
        status, response = aapi.add_list_row(
            list_id,
            [ioc.attribute_type, 'Comments'],
            [ioc.value, ioc.description])
        status_code = status
        error_message = None
    except Exception as e:
        status_code = None
        error_message = str(e)
    # Сохраняем статус в базе данных
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ioc_statuses (ioc_id, service_url, status_code, error_message) VALUES (?, ?, ?, ?)",
            (ioc_id, data['url'], status_code, error_message)
        )
        conn.commit()

@app.post("/add_ioc")
async def add_ioc(data: dict, background_tasks: BackgroundTasks):
    """Добавляет IOC в базу данных и отправляет его в другие сервисы."""
    try:
        ioc = IOC(**data)
        # Вставка в базу данных
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO iocs (attribute_type, value, description) VALUES (?, ?, ?)",
                (ioc.attribute_type, ioc.value, ioc.description),
            )
            ioc_id = cursor.lastrowid
            conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="IOC уже существует."
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=e.errors()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Произошла непредвиденная ошибка: {str(e)}"
        )
    
    # Запускаем фоновые задачи
    for service in services:
        if service['type'] == 'kuma':
            background_tasks.add_task(
                send_ioc_to_kuma,
                service['data'],
                ioc_id,
                ioc)
        elif service['type'] == 'arcsight':
            background_tasks.add_task(
                send_ioc_to_arcsight,
                service['data'],
                ioc_id,
                ioc)
        # Добавьте обработку для других типов сервисов, если необходимо
    
    return {"message": "IOC успешно добавлен и отправляется в другие сервисы.", "ioc_id": ioc_id, "services_count": len(services)}

# Остальные эндпоинты остаются без изменений

@app.get("/get_all_iocs")
async def get_all_iocs():
    """Возвращает все IOC из базы данных."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, attribute_type, value, description FROM iocs")
        rows = cursor.fetchall()
    return [
        {"id": row[0], "attribute_type": row[1], "value": row[2], "description": row[3]}
        for row in rows
    ]

@app.post("/search_ioc")
async def search_ioc(query: SearchQuery):
    """Поиск IOC по attribute_type и/или value."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            sql_query = "SELECT id, attribute_type, value, description FROM iocs WHERE 1=1"
            params = []
            if query.attribute_type:
                sql_query += " AND attribute_type = ?"
                params.append(query.attribute_type)
            if query.value:
                sql_query += " AND value LIKE ?"
                params.append(f"%{query.value}%")
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()

        results = [
            {"id": row[0], "attribute_type": row[1], "value": row[2], "description": row[3]}
            for row in rows
        ]
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.delete("/delete_ioc_by_id/{id}")
async def delete_ioc_by_id(id: int):
    """Удаляет IOC по ID."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM iocs WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"IOC с ID {id} не найден.")
        cursor.execute("DELETE FROM iocs WHERE id = ?", (id,))
        conn.commit()
    return {"message": f"IOC с ID {id} успешно удален."}

@app.get("/ioc_status/{ioc_id}")
async def get_ioc_status(ioc_id: int):
    """Возвращает статусы отправки IOC в другие сервисы."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT service_url, status_code, error_message FROM ioc_statuses WHERE ioc_id = ?",
            (ioc_id,)
        )
        rows = cursor.fetchall()
    statuses = [
        {"service_url": row[0], "status_code": row[1], "error_message": row[2]}
        for row in rows
    ]
    return {"ioc_id": ioc_id, "statuses": statuses}
