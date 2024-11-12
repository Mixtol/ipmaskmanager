from pydantic import BaseModel, IPvAnyNetwork, IPvAnyAddress
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from typing import List, Union, Optional
import sqlite3
import ipaddress

# Инициализация FastAPI
app = FastAPI()

# Подключение папки со статикой
app.mount("/static", StaticFiles(directory="static"), name='static')

# Создание базы данных SQLite
DB_FILE = "subnets.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Создаем таблицу с уникальным ограничением по network + company
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subnets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            network TEXT NOT NULL,
            company TEXT NOT NULL,
            description TEXT,
            UNIQUE(network, company) -- Уникальное ограничение
        )
        """)
        conn.commit()

init_db()

# Модель для добавления записи
class Subnet(BaseModel):
    network: IPvAnyNetwork
    company: str
    description: Optional[str] = None

# Модель для поиска
class SearchQuery(BaseModel):
    query: Optional[str] = None
    company: Optional[str] = None


@app.get("/")
async def serve_index():
    """Главная страница
    """
    return FileResponse("static/index.html")


@app.post("/add_subnet")
async def add_subnet(subnet: Subnet):
    """
    Добавляет подсеть в базу данных.
    """
    try:
        IPvAnyNetwork(subnet.network)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO subnets (network, company, description) VALUES (?, ?, ?)",
                (str(subnet.network), subnet.company, subnet.description),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Subnet already exists for this company.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subnet format.")
    return {"message": "Subnet added successfully."}


@app.get("/get_all_subnets")
async def get_all_subnets():
    """
    Возвращает все записи в базе данных.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, network, company, description FROM subnets")
        rows = cursor.fetchall()
    return [
        {"id": row[0], "network": row[1], "company": row[2], "description": row[3]}
        for row in rows
    ]


@app.get("/get_companies")
async def get_companies():
    """
    Возвращает список всех уникальных компаний.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT company FROM subnets")
        rows = cursor.fetchall()
    return [row[0] for row in rows]
 

@app.post("/search_subnet")
async def search_subnet(query: SearchQuery):
    """
    Поиск записей по IP/подсети и/или компании.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, network, company, description FROM subnets")
            rows = cursor.fetchall()

        results = []

        # Если указана только компания
        if query.company and not query.query:
            results = [
                {"id": row[0], "network": row[1], "company": row[2], "description": row[3]}
                for row in rows if row[2] == query.company
            ]

        # Если указан только IP/сеть
        elif query.query and not query.company:
            try:
                search_object = ipaddress.ip_network(query.query, strict=False)
                for row in rows:
                    db_network = ipaddress.ip_network(row[1])
                    if search_object.subnet_of(db_network) or db_network.subnet_of(search_object):
                        results.append({
                            "id": row[0],
                            "network": row[1],
                            "company": row[2],
                            "description": row[3]
                        })
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid IP or network format.")

        # Если указаны оба параметра
        elif query.query and query.company:
            try:
                search_object = ipaddress.ip_network(query.query, strict=False)
                for row in rows:
                    db_network = ipaddress.ip_network(row[1])
                    if row[2] == query.company and (
                        search_object.subnet_of(db_network) or db_network.subnet_of(search_object)
                    ):
                        results.append({
                            "id": row[0],
                            "network": row[1],
                            "company": row[2],
                            "description": row[3]
                        })
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid IP or network format.")

        # Если ничего не указано
        else:
            results = [
                {"id": row[0], "network": row[1], "company": row[2], "description": row[3]}
                for row in rows
            ]

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")





@app.delete("/delete_subnet")
async def delete_subnet(subnet: Subnet):
    """
    Удаляет запись по подсети и компании.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Проверяем, существует ли такая комбинация network + company
        cursor.execute(
            "SELECT id FROM subnets WHERE network = ? AND company = ?",
            (str(subnet.network), subnet.company)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Network {subnet.network} for company {subnet.company} not found."
            )

        # Удаляем запись
        cursor.execute(
            "DELETE FROM subnets WHERE network = ? AND company = ?",
            (str(subnet.network), subnet.company)
        )
        conn.commit()

    return {"message": f"Subnet {subnet.network} for company {subnet.company} deleted successfully."}


@app.delete("/delete_subnet_index/{id}")
async def delete_subnet_index(id: int):
    """
    Удаляет подсеть по ID.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM subnets WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Subnet with ID {id} not found.")
        cursor.execute("DELETE FROM subnets WHERE id = ?", (id,))
        conn.commit()
    return {"message": f"Subnet with ID {id} deleted successfully."}


