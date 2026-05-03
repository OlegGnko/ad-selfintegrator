# Деплой AD SelfIntegrator

## Вариант A — Hetzner VPS (рекомендуется, €4/мес)

**Подходит для production.** Сервер в Германии, данные в EU, полный контроль.

### 1. Создать сервер

1. Зарегистрироваться на hetzner.com
2. Cloud Console → New Server:
   - Location: **Nuremberg** или **Helsinki**
   - Image: **Ubuntu 24.04**
   - Type: **CX22** (2 CPU, 4 GB RAM — €3.92/мес)
   - SSH key: добавить свой публичный ключ
3. Запомнить IP сервера (например `123.45.67.89`)

### 2. Первоначальная настройка сервера

```bash
# Зайти на сервер
ssh root@123.45.67.89

# Обновить систему
apt update && apt upgrade -y

# Установить Docker
curl -fsSL https://get.docker.com | sh

# Установить Nginx
apt install nginx -y
```

### 3. Загрузить проект на сервер

На своём Mac (в папке проекта):
```bash
# Скопировать проект на сервер (первый раз)
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  /Users/Oleg/Desktop/AI_work/AD_SelfIntegrator/ \
  root@123.45.67.89:/opt/ad-selfintegrator/
```

### 4. Создать .env на сервере

```bash
ssh root@123.45.67.89
cat > /opt/ad-selfintegrator/.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-api03-ВАШ_КЛЮЧ_ЗДЕСЬ
EOF
```

### 5. Создать Docker-файлы

Создать `/opt/ad-selfintegrator/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Создать `/opt/ad-selfintegrator/docker-compose.yml`:
```yaml
services:
  app:
    build: .
    restart: always
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./sessions.db:/app/sessions.db
    env_file:
      - .env
```

### 6. Запустить приложение

```bash
cd /opt/ad-selfintegrator
docker compose up -d --build
```

### 7. Настроить Nginx (reverse proxy)

```bash
cat > /etc/nginx/sites-available/selfintegrator << 'EOF'
server {
    listen 80;
    server_name ВАШ_ДОМЕН.pl;  # или IP сервера

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
EOF

ln -s /etc/nginx/sites-available/selfintegrator /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 8. HTTPS (если есть домен)

```bash
apt install certbot python3-certbot-nginx -y
certbot --nginx -d ВАШ_ДОМЕН.pl
```

### Обновление после изменений кода

```bash
# На Mac: синхронизировать файлы
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  /Users/Oleg/Desktop/AI_work/AD_SelfIntegrator/ \
  root@123.45.67.89:/opt/ad-selfintegrator/

# На сервере: перезапустить
ssh root@123.45.67.89 "cd /opt/ad-selfintegrator && docker compose up -d --build"
```

---

## Вариант B — Railway.app (быстрый старт, $5/мес)

Подходит для тестирования, без настройки сервера.

1. Зарегистрироваться на railway.app
2. New Project → Deploy from GitHub repo
   - Залить проект на GitHub (приватный репозиторий)
3. В Railway добавить переменную окружения: `ANTHROPIC_API_KEY`
4. Railway автоматически обнаружит Python и запустит через `uvicorn`

**Минус:** SQLite не персистентный между деплоями — нужен Railway PostgreSQL (добавляется одной кнопкой, но требует доработки кода).

---

## Persistent sessions (уже реализовано)

После деплоя каждая сессия сохраняется в `sessions.db` (SQLite файл).

- Пользователь видит уникальную ссылку вида `https://ВАШ_ДОМЕН.pl/?session=<uuid>`
- Может скопировать её и вернуться позже — разговор продолжится с того места
- При Hetzner данные хранятся вечно (файл `sessions.db` на сервере)
- При Railway нужен внешний PostgreSQL (иначе данные сбрасываются при деплое)
