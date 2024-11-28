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

from modules.arcsight_api import ArcSightAPI
from modules.kuma_api import KumaRestAPIv2

### Пиздец местного разлива
main_core = {
    "url": "https://0400kumcore01.pv.mts.ru",
    "token": os.environ.get('KUMA_MAIN', None),
    # "FQDN":"c3677a36-3dd4-440e-b574-1f872f73258b",
    # "src-ip":"fb4ff0fa-1c35-4db0-a86f-f6b34857d4e3"
    "FQDN":"35ef03b2-5824-4120-ab36-ae961cdb851e",
    "src-ip":"35ef03b2-5824-4120-ab36-ae961cdb851e"
}
mts_bank = {
    "url": "https://0001kumcore01.msk.mts.ru",
    "token": os.environ.get('KUMA_PAO', None),
    "FQDN":"a4db230f-e2ea-48e4-b8cd-c0b721d21d04",
    "src-ip":"da86140c-0b22-4338-aa24-ba3640b5cf7c"
}
arc_sight = {
    "url": "https://0400arc-esm-mb01.pv.mts.ru",
    "token": os.environ.get('ARC_TOKEN', None),
    #"FQDN":"Hvu-5sIwBABDGoBZZHVhMTA%3D%3D",
    #"src-ip":"HRh56KosBABD2lRvZadoKag%3D%3D"
    "FQDN":"HCInfb5MBABCAJYwYVXf%2BMg%3D%3D",
}
misp = {
    "url": "https://0400socti01.pv.mts.ru",
    "token": os.environ.get('MISP_TOKEN', None),
} 
####

# Initialize FastAPI
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name='static')

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Database file
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
        elif attribute_type in ["src-ip|port","dst-ip|port"]:
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


# Model for search queries
class SearchQuery(BaseModel):
    attribute_type: Optional[AttributeType] = None
    value: Optional[str] = None
    
    
async def send_ioc_to_kuma(data:dict, ioc_id, ioc:IOC):
    #async with aiohttp.ClientSession() as session:
        # try:
        #     async with session.post(url, json=ioc.dict()) as response:
        #         status = response.status
        # except Exception as e:
        #     # Если произошла ошибка, можно установить статус как None или специальное значение
        #     status = None
        try:
            kapi = KumaRestAPIv2(data['url'], data['token'])
            status, response = kapi.add_dictionary_row(
                data[ioc.attribute_type],
                ioc.value,
                {"value":ioc.description})
            # async with session.post('http://127.0.0.1:8000/') as response:
            #     status = response.status
        except Exception as e:
            # Если произошла ошибка, можно установить статус как None или специальное значение
            status = e
        # Сохраняем статус в базе данных
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ioc_statuses (ioc_id, service_url, status_code) VALUES (?, ?, ?)",
                (ioc_id, data['url'], status)
            )
            conn.commit()

async def send_ioc_to_arcsight(data:dict, ioc_id, ioc:IOC):
    #async with aiohttp.ClientSession() as session:
        try:
            aapi = ArcSightAPI(data['url'], data['token'])
            status, response = aapi.add_list_row(
                data[ioc.attribute_type],
                [ioc.attribute_type, 'Comments'],
                [ioc.value, ioc.description])
            # async with session.post(url, json=ioc.dict()) as response:
            #     status = response.status
        except Exception as e:
            # Если произошла ошибка, можно установить статус как None или специальное значение
            status = None
        # Сохраняем статус в базе данных
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ioc_statuses (ioc_id, service_url, status_code) VALUES (?, ?, ?)",
                (ioc_id, data['url'], status)
            )
            conn.commit()


@app.get("/")
async def serve_index():
    """Main page"""
    return FileResponse("static/index.html")


@app.post("/add_ioc")
async def add_ioc(data:dict, background_tasks: BackgroundTasks):
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
    background_tasks.add_task(
        send_ioc_to_kuma,
        mts_bank,
        ioc_id,
        ioc)
    # background_tasks.add_task(
    #     send_ioc_to_kuma,
    #     main_core,
    #     ioc_id,
    #     ioc)
    background_tasks.add_task(
        send_ioc_to_arcsight,
        arc_sight,
        ioc_id,
        ioc)
    return {"message": "IOC успешно добавлен и отправляется в другие сервисы.", "ioc_id": ioc_id}


@app.get("/get_all_iocs")
async def get_all_iocs():
    """Returns all IOC entries in the database."""
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
    """Searches for IOCs based on attribute_type and/or value."""
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

@app.delete("/delete_ioc")
async def delete_ioc(ioc: IOC):
    """Deletes an IOC based on attribute_type and value."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Check if such an IOC exists
        cursor.execute(
            "SELECT id FROM iocs WHERE attribute_type = ? AND value = ?",
            (ioc.attribute_type, ioc.value)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"IOC with type {ioc.attribute_type} and value {ioc.value} not found."
            )
        # Delete the IOC
        cursor.execute(
            "DELETE FROM iocs WHERE attribute_type = ? AND value = ?",
            (ioc.attribute_type, ioc.value)
        )
        conn.commit()
    return {"message": f"IOC with type {ioc.attribute_type} and value {ioc.value} deleted successfully."}

@app.delete("/delete_ioc_by_id/{id}")
async def delete_ioc_by_id(id: int):
    """Deletes an IOC by ID."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM iocs WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"IOC with ID {id} not found.")
        cursor.execute("DELETE FROM iocs WHERE id = ?", (id,))
        conn.commit()
    return {"message": f"IOC with ID {id} deleted successfully."}


@app.get("/ioc_status/{ioc_id}")
async def get_ioc_status(ioc_id: int):
    """Возвращает статусы отправки IOC в другие сервисы."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT service_url, status_code FROM ioc_statuses WHERE ioc_id = ?",
            (ioc_id,)
        )
        rows = cursor.fetchall()
    statuses = [
        {"service_url": row[0], "status_code": row[1]}
        for row in rows
    ]
    return {"ioc_id": ioc_id, "statuses": statuses}
