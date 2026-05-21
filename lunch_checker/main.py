#!/usr/bin/env python3
"""
Запускается каждый будний день в 11:00 (Warsaw) через GitHub Actions.
Собирает ланч-меню с 4 Facebook-страниц и отправляет в Telegram.
"""

import os
from datetime import date

import anthropic

from scraper import RESTAURANTS, scrape_all
from telegram_bot import send


def _extract_menu(client: anthropic.Anthropic, restaurant: str, raw: str, today: str) -> str:
    if raw.startswith("__error__"):
        return "⚠️ Не удалось загрузить страницу"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Ты помогаешь найти ланч-меню ресторана.\n\n"
                    f"Ресторан: {restaurant}\n"
                    f"Дата: {today}\n\n"
                    f"Ниже — текст, извлечённый со страницы Facebook.\n"
                    f"Найди ланч/обеденное меню на сегодня ({today}).\n"
                    f"Если нашёл — выведи только блюда (и цены если есть), кратко.\n"
                    f"Если меню на сегодня не найдено — напиши только: Меню не опубликовано\n\n"
                    f"Текст страницы:\n{raw[:6000]}"
                ),
            }
        ],
    )
    return response.content[0].text.strip()


def main() -> None:
    today = date.today().strftime("%d.%m.%Y")
    print(f"=== Lunch checker {today} ===")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("Scraping Facebook pages...")
    raw_data = scrape_all()

    lines = [f"🍽 <b>Ланч-меню на {today}</b>"]
    for r in RESTAURANTS:
        name = r["name"]
        menu = _extract_menu(client, name, raw_data.get(name, "__error__: missing"), today)
        lines.append(f"\n<b>{name}</b>\n{menu}")

    message = "\n".join(lines)
    print("Sending to Telegram...")
    send(message)
    print("Done.")


if __name__ == "__main__":
    main()
