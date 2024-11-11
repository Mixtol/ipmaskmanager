# IpSearch service

Сервис для хранения и быстрого поиска IP-адресов по подсетям заказчика.
https://confluence.mts.ru/pages/viewpage.action?pageId=1362735821

Далее будет интегрирован в офенсис как микросервис со свой БД.

## Описание методов

### 1. Создание записи (`/add_subnet`)
**Метод:** `POST`  
**Описание:** Добавляет запись в базу данных, если комбинация `network` и `company` уникальна.  

Пример запроса:
```json
{
  "network": "192.168.1.0/24",
  "company": "Example Corp",
  "description": "Corporate network"
}
```

Пример ответа:
```json
{
  "message": "Subnet added successfully."
}
```

Если подсеть уже существует для этой компании:
```json
{
  "detail": "Network 192.168.1.0/24 already exists for company ExampleCorp."
}
```

### 2. Удаление записи (`/delete_subnet`)
**Метод:** `DELETE`  
**Описание:** Удаляет запись из базы данных по комбинации `network` и `company`.

Пример запроса:
```sh
DELETE /delete_subnet
```

```json
{
  "network": "192.168.1.0/24",
  "company": "Example Corp",
}
```

Пример ответа (200):
```json
{
  "message": "Subnet 192.168.1.0/24 for company Example Corp deleted successfully."
}
```

Пример ответа (запись не найдена):

```json
{
  "detail": "Network 192.168.1.0/24 for company Example Corp not found."
}
```


### 3. Поиск записей (`/search_subnet`)
**Метод:** `POST`  
**Описание:** Принимает IP-адрес, подсеть или название компании и возвращает все совпадения.

Пример запроса (по IP):
```json
{
  "query": "192.168.1.1"
}
```

Пример запроса (по подсети):
```json
{
  "query": "192.168.1.0/24"
}
```

Пример запроса (по компании):
```json
{
  "company": "Example Corp"
}
```

Пример ответа:
```json
[
  {
    "network": "192.168.1.0/24",
    "company": "Example Corp",
    "description": "Corporate network"
  }
]
```

## Запуск приложения

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```