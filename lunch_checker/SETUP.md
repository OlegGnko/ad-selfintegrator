# Настройка Lunch Checker

## Как это работает

Каждый будний день в 11:00 (Warsaw) GitHub Actions:
1. Запускает Playwright — открывает 4 страницы Facebook с твоими cookies
2. Извлекает текст постов
3. Claude (Haiku) находит в тексте сегодняшнее меню
4. Отправляет итог в Telegram

---

## Шаг 1 — Извлечь cookies из Facebook

### В Chrome / Edge:
1. Установи расширение **[Cookie-Editor](https://cookie-editor.com/)** (бесплатное)
2. Зайди на `https://www.facebook.com` и убедись, что ты залогинен
3. Нажми на иконку расширения Cookie-Editor
4. Нажми кнопку **Export** → **Export as JSON**
5. Скопируй весь JSON (это и есть значение для `FB_COOKIES`)

> ⚠️ Cookies действуют несколько месяцев. Если скрипт перестанет авторизовываться — повтори этот шаг.

---

## Шаг 2 — Добавить Secrets в GitHub

Открой свой репозиторий на GitHub → **Settings → Secrets and variables → Actions → New repository secret**

Добавь 4 секрета:

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `TELEGRAM_BOT_TOKEN` | `8567317006:AAEVbalzFtK3NzYyI6oYeUiJeAhQsuv3j3Q` |
| `TELEGRAM_CHAT_ID` | твой числовой ID из @userinfobot |
| `FB_COOKIES` | JSON из Cookie-Editor (весь массив `[{...}, {...}]`) |

---

## Шаг 3 — Пуш и тест

```bash
git add .github/workflows/lunch_check.yml lunch_checker/
git commit -m "add: lunch menu checker"
git push
```

Затем на GitHub: **Actions → Daily Lunch Menu → Run workflow** — проверь что всё работает вручную.

---

## Смена времени (зима/лето)

Файл `.github/workflows/lunch_check.yml`, строка `cron`:
- **Лето (CEST, UTC+2):** `"0 9 * * 1-5"` — сейчас стоит это
- **Зима (CET, UTC+1):** `"0 10 * * 1-5"`
