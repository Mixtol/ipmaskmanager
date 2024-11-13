# IpSearch Service

**Сервис для управления и поиска IP-адресов и подсетей.**

Этот сервис позволяет хранить подсети, привязывать их к компаниям, добавлять описания и выполнять быстрый поиск по IP-адресам, подсетям или компаниям.

---

## 📚 Методы API

### 1. Добавление подсети (`/add_subnet`)
**Метод:** `POST`  
**Описание:** Добавляет подсеть в базу данных. Если комбинация `network` и `company` уже существует, вернётся ошибка.  

**Пример запроса:**
```json
{
  "network": "192.168.1.0/24",
  "company": "Example Corp",
  "description": "Corporate network"
}
```

**Пример успешного ответа:**
```json
{
  "message": "Subnet added successfully."
}
```

**Пример ошибки (если подсеть уже существует):**
```json
{
  "detail": "Subnet already exists for this company."
}
```

---

### 2. Удаление подсети по комбинации (`/delete_subnet`)
**Метод:** `DELETE`  
**Описание:** Удаляет подсеть из базы данных по комбинации `network` и `company`.

**Пример запроса:**
```json
{
  "network": "192.168.1.0/24",
  "company": "Example Corp"
}
```

**Пример успешного ответа:**
```json
{
  "message": "Subnet 192.168.1.0/24 for company Example Corp deleted successfully."
}
```

**Пример ошибки (если запись не найдена):**
```json
{
  "detail": "Network 192.168.1.0/24 for company Example Corp not found."
}
```

---

### 3. Удаление подсети по ID (`/delete_subnet_index/{id}`)
**Метод:** `DELETE`  
**Описание:** Удаляет запись из базы данных по ID.

**Пример запроса:**
```http
DELETE /delete_subnet_index/5
```

**Пример успешного ответа:**
```json
{
  "message": "Subnet with ID 5 deleted successfully."
}
```

**Пример ошибки (если ID не найден):**
```json
{
  "detail": "Subnet with ID 5 not found."
}
```

---

### 4. Получение всех записей (`/get_all_subnets`)
**Метод:** `GET`  
**Описание:** Возвращает список всех записей в базе данных.

**Пример успешного ответа:**
```json
[
  {
    "id": 1,
    "network": "192.168.1.0/24",
    "company": "Example Corp",
    "description": "Corporate network"
  },
  {
    "id": 2,
    "network": "10.0.0.0/8",
    "company": "Another Corp",
    "description": "Internal network"
  }
]
```

---

### 5. Получение списка компаний (`/get_companies`)
**Метод:** `GET`  
**Описание:** Возвращает список уникальных названий компаний, сохранённых в базе данных.

**Пример успешного ответа:**
```json
[
  "Example Corp",
  "Another Corp"
]
```

---

### 6. Поиск записей (`/search_subnet`)
**Метод:** `POST`  
**Описание:** Выполняет поиск по IP/подсети и/или названию компании.  
Если параметры не указаны, возвращаются все записи.

**Пример запроса (по IP):**
```json
{
  "query": "192.168.1.1"
}
```

**Пример запроса (по подсети):**
```json
{
  "query": "192.168.1.0/24"
}
```

**Пример запроса (по компании):**
```json
{
  "company": "Example Corp"
}
```

**Пример успешного ответа:**
```json
[
  {
    "id": 1,
    "network": "192.168.1.0/24",
    "company": "Example Corp",
    "description": "Corporate network"
  }
]
```

**Пример ошибки (некорректный формат запроса):**
```json
{
  "detail": "Invalid IP or network format."
}
```

---

## 🚀 Запуск приложения

### Требования
- Python 3.9+
- Зависимости из `requirements.txt`:
  ```bash
  pip install -r requirements.txt
  ```

### Шаги для локального запуска
0. Инициализируйте базу данных (автоматически при старте).
1. Запустите приложение с помощью Uvicorn:
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```
2. Перейти по адресу:
   ```
   http://127.0.0.1:8000
   ```

---

## 🛠 Разработка и структура

### Структура проекта
```
.
├── app.py                # Основной файл приложения FastAPI
├── subnets.db            # SQLite база данных
├── static/               # Статические файлы
│   ├── css/
│   │   └── styles.css    # Стили фронтенда
│   ├── js/
│   │   └── app.js        # Логика фронтенда
│   └── favicon.ico       # Иконка приложения
└── templates/
    └── index.html        # Главная страница
```

### Основные технологии
- **FastAPI:** Для создания API.
- **SQLite:** Лёгкая база данных для хранения данных.
- **HTML, CSS, JS:** Фронтенд приложения.

---
