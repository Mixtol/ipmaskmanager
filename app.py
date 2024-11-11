from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, IPvAnyNetwork, IPvAnyAddress
from typing import List, Union, Optional
import sqlite3
import ipaddress

# Инициализация FastAPI
app = FastAPI()

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
    query: Union[IPvAnyAddress, IPvAnyNetwork, None] = None
    company: Optional[str] = None


@app.post("/add_subnet")
async def add_subnet(subnet: Subnet):
    """
    Добавляет новую подсеть в базу данных.
    Если подсеть уже существует для той же компании, возвращает ошибку.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Проверяем, существует ли такая комбинация network + company
        cursor.execute(
            "SELECT id FROM subnets WHERE network = ? AND company = ?",
            (str(subnet.network), subnet.company)
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"Network {subnet.network} already exists for company {subnet.company}."
            )

        # Добавляем новую запись
        cursor.execute("""
        INSERT INTO subnets (network, company, description)
        VALUES (?, ?, ?)
        """, (str(subnet.network), subnet.company, subnet.description))
        conn.commit()

    return {"message": "Subnet added successfully."}


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


@app.post("/search_subnet")
async def search_subnets(query: SearchQuery):
    """
    Ищет записи по IP-адресу, подсети или компании.
    Возвращает массив всех совпадений.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT network, company, description FROM subnets")
        rows = cursor.fetchall()

    matches = []

    # Если передан IP-адрес или подсеть
    if query.query:
        search_object = (
            ipaddress.ip_address(query.query)
            if isinstance(query.query, (str, ipaddress.IPv4Address, ipaddress.IPv6Address))
            else ipaddress.ip_network(query.query)
        )

        for network, company, description in rows:
            db_network = ipaddress.ip_network(network)
            # Проверяем, входит ли IP/подсеть в запись БД
            if (
                isinstance(search_object, ipaddress.IPv4Address)
                or isinstance(search_object, ipaddress.IPv6Address)
            ):
                if search_object in db_network:
                    matches.append({"network": network, "company": company, "description": description})
            elif isinstance(search_object, ipaddress.IPv4Network) or isinstance(search_object, ipaddress.IPv6Network):
                if search_object.subnet_of(db_network) or db_network.subnet_of(search_object):
                    matches.append({"network": network, "company": company, "description": description})

    # Если передана компания
    if query.company:
        for network, company, description in rows:
            if company == query.company:
                matches.append({"network": network, "company": company, "description": description})

    return matches