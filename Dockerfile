# Используем базовый образ Python
FROM python:slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Подключаем нетфликс
RUN printf '[global] \n\
timeout=360 \n\
trusted-host = nexus.services.mts.ru \n\
index-url=https://nexus.services.mts.ru/repository/pip/simple/ \n\
index=https://nexus.services.mts.ru/repository/pip/' > /etc/pip.conf

# Устанавливаем зависимости без кэша а то докер ругается
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --progress-bar off --no-build-isolation -r requirements.txt

# Копируем код приложения
COPY . .

# Указываем порт, который будет слушать приложение
EXPOSE 8000

# Команда для запуска приложения
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]