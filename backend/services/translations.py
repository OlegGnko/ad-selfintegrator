"""
UI and document translations for PL / EN / RU.

Usage:
    from services.translations import T, scope_item
    t = T["en"]
    translated_name = scope_item("Szkolenie zespołu...", "en")
"""

# ---------------------------------------------------------------------------
# Proposal / document labels
# ---------------------------------------------------------------------------

T: dict[str, dict] = {
    "pl": {
        # Header
        "doc_title":          "Oferta handlowa",
        "tag":                "Wdrożenia Bitrix24 · CRM · Automatyzacja",
        "lime_bar_label":     "Wdrożenie CRM Bitrix24",
        "lime_bar_validity":  "Ważność oferty",
        "days":               "dni",
        # Parties
        "executor":           "Wykonawca",
        "client":             "Zamawiający",
        # Summary boxes
        "value_net":          "Wartość netto",
        "value_gross":        "Wartość brutto",
        "hours_total":        "Łączne godziny",
        "delivery_time":      "Czas realizacji",
        "weeks_6":            "6 tyg.",
        # Scope table
        "h1_scope":           "1. Zakres prac",
        "col_no":             "Lp.",
        "col_item":           "Pozycja",
        "col_hours":          "Godz.",
        "col_price":          "Cena netto",
        "total_net":          "RAZEM NETTO",
        "total_gross":        "RAZEM BRUTTO (VAT 23%)",
        "rate_note":          "Stawka: 250 PLN netto/godz. · Wszystkie ceny netto, VAT 23%.",
        "free_label":         "gratis",
        # License
        "h2_license":         "2. Licencja Bitrix24",
        "license_desc":       "Koszt licencji Bitrix24 <strong>nie jest wliczony</strong> w cenę wdrożenia — Zamawiający nabywa ją bezpośrednio od Bitrix24. Poniżej przedstawiamy dostępne plany i rekomendację dla Państwa firmy.",
        "col_plan":           "Plan",
        "col_users":          "Użytkownicy",
        "col_price_mo":       "Cena/mies.",
        "col_features":       "Kluczowe funkcje",
        "rec_prefix":         "Rekomendacja dla",
        "rec_plan":           "plan",
        "prices_note":        "Ceny mogą ulec zmianie — aktualne stawki na <strong>bitrix24.pl</strong>.",
        # License plans descriptions
        "plan_free_feat":     "Podstawowy CRM, zadania, czat — bez automatyzacji i zaawansowanych raportów",
        "plan_basic_feat":    "CRM, maile, 24 GB dysk, podstawowe automatyzacje",
        "plan_std_feat":      "Pełny CRM, automatyzacje, marketing, 100 GB dysk",
        "plan_pro_feat":      "Wszystko z Standard + HR, serwis, zaawansowana analityka, 1024 GB",
        "plan_ent_feat":      "Pełna platforma, wiele oddziałów, dedykowany serwer, SLA",
        # Timeline
        "h3_timeline":        "3. Harmonogram realizacji",
        "week_label":         "Tydzień",
        # How it works
        "h4_how":             "4. Jak przebiega wdrożenie?",
        "phase_analysis":     "<strong>Analiza</strong> — mapujemy procesy biznesowe i ustalamy konfigurację podczas spotkania online.",
        "phase_config":       "<strong>Konfiguracja</strong> — ustawiamy lejki, automatyzacje, pola i uprawnienia w Bitrix24.",
        "phase_integrations": "<strong>Integracje</strong> — podłączamy telefonie, formularze i inne systemy.",
        "phase_import":       "<strong>Import danych</strong> — przenosimy kontakty, firmy i historię z obecnych narzędzi.",
        "phase_training":     "<strong>Szkolenia i odbiór</strong> — szkolenie online dla zespołu + nadzór przez pierwsze 2 tygodnie.",
        # Terms
        "h5_terms":           "5. Warunki handlowe",
        "payment":            "Płatność",
        "advance":            "Zaliczka",
        "delivery":           "Termin realizacji",
        "guarantee":          "Gwarancja",
        "support":            "Wsparcie startowe",
        "payment_val":        "50% + 50%",
        "delivery_val":       "do 6 tygodni",
        "guarantee_val":      "12 miesięcy",
        "support_val":        "2 tygodnie gratis",
        # Guarantees
        "h6_guarantees":      "6. Nasze gwarancje",
        "g1_title":           "Stały opiekun projektu",
        "g1_text":            "Jeden PM odpowiada za cały projekt — pełna odpowiedzialność i komunikacja.",
        "g2_title":           "Certyfikowani specjaliści",
        "g2_text":            "Zespół z certyfikatami Bitrix24 i kilkuletnim doświadczeniem wdrożeniowym.",
        "g3_title":           "Cena stała w umowie",
        "g3_text":            "Żadnych ukrytych kosztów. Zmiany zakresu — tylko za osobnym aneksem.",
        # Acceptance
        "h7_accept":          "7. Akceptacja oferty",
        "accept_text":        "W celu akceptacji prosimy o podpisanie umowy i wpłatę zaliczki na rachunek bankowy:",
        "contact_label":      "Kontakt:",
        "sig_executor":       "Wykonawca",
        "sig_client":         "Zamawiający",
        # Call manager (chat UI)
        "call_manager_btn":       "Zadzwoń do managera",
        "call_manager_sent":      "Twój zapytanie zostało przekazane managerowi. Odezwie się do Ciebie tak szybko, jak tylko to możliwe!",
        "call_manager_error":     "Nie udało się wysłać zapytania. Proszę napisz bezpośrednio na info@alphadigital.pl",
    },

    "en": {
        "doc_title":          "Commercial Proposal",
        "tag":                "Bitrix24 Implementation · CRM · Automation",
        "lime_bar_label":     "Bitrix24 CRM Implementation",
        "lime_bar_validity":  "Offer validity",
        "days":               "days",
        "executor":           "Service Provider",
        "client":             "Client",
        "value_net":          "Net value",
        "value_gross":        "Gross value",
        "hours_total":        "Total hours",
        "delivery_time":      "Timeline",
        "weeks_6":            "6 wks.",
        "h1_scope":           "1. Scope of Work",
        "col_no":             "No.",
        "col_item":           "Item",
        "col_hours":          "Hours",
        "col_price":          "Net price",
        "total_net":          "TOTAL NET",
        "total_gross":        "TOTAL GROSS (VAT 23%)",
        "rate_note":          "Rate: 250 PLN net/hour · All prices net, VAT 23%.",
        "free_label":         "free",
        "h2_license":         "2. Bitrix24 License",
        "license_desc":       "The Bitrix24 license cost is <strong>not included</strong> in the implementation price — the Client purchases it directly from Bitrix24. Below are the available plans and our recommendation for your company.",
        "col_plan":           "Plan",
        "col_users":          "Users",
        "col_price_mo":       "Price/mo.",
        "col_features":       "Key features",
        "rec_prefix":         "Recommendation for",
        "rec_plan":           "plan",
        "prices_note":        "Prices may change — current rates at <strong>bitrix24.com</strong>.",
        "plan_free_feat":     "Basic CRM, tasks, chat — no automations or advanced reports",
        "plan_basic_feat":    "CRM, email, 24 GB disk, basic automations",
        "plan_std_feat":      "Full CRM, automations, marketing, 100 GB disk",
        "plan_pro_feat":      "Everything in Standard + HR, service desk, advanced analytics, 1024 GB",
        "plan_ent_feat":      "Full platform, multiple branches, dedicated server, SLA",
        "h3_timeline":        "3. Project Timeline",
        "week_label":         "Week",
        "h4_how":             "4. How does the implementation work?",
        "phase_analysis":     "<strong>Analysis</strong> — we map business processes and define configuration during an online meeting.",
        "phase_config":       "<strong>Configuration</strong> — we set up pipelines, automations, fields and permissions in Bitrix24.",
        "phase_integrations": "<strong>Integrations</strong> — we connect telephony, forms and other systems.",
        "phase_import":       "<strong>Data import</strong> — we migrate contacts, companies and history from existing tools.",
        "phase_training":     "<strong>Training & handover</strong> — online team training + supervision for the first 2 weeks.",
        "h5_terms":           "5. Commercial Terms",
        "payment":            "Payment",
        "advance":            "Advance payment",
        "delivery":           "Delivery time",
        "guarantee":          "Warranty",
        "support":            "Initial support",
        "payment_val":        "50% + 50%",
        "delivery_val":       "up to 6 weeks",
        "guarantee_val":      "12 months",
        "support_val":        "2 weeks free",
        "h6_guarantees":      "6. Our Guarantees",
        "g1_title":           "Dedicated Project Manager",
        "g1_text":            "One PM is responsible for the entire project — full accountability and communication.",
        "g2_title":           "Certified Specialists",
        "g2_text":            "Team with Bitrix24 certifications and years of implementation experience.",
        "g3_title":           "Fixed Price in Contract",
        "g3_text":            "No hidden costs. Scope changes only through a separate amendment.",
        "h7_accept":          "7. Proposal Acceptance",
        "accept_text":        "To accept this proposal, please sign the contract and transfer the advance payment to our bank account:",
        "contact_label":      "Contact:",
        "sig_executor":       "Service Provider",
        "sig_client":         "Client",
        "call_manager_btn":   "Talk to a manager",
        "call_manager_sent":  "Your request has been forwarded to our manager. They will contact you as soon as possible!",
        "call_manager_error": "Failed to send request. Please write directly to info@alphadigital.pl",
    },

    "ru": {
        "doc_title":          "Коммерческое предложение",
        "tag":                "Внедрение Bitrix24 · CRM · Автоматизация",
        "lime_bar_label":     "Внедрение CRM Bitrix24",
        "lime_bar_validity":  "Срок действия КП",
        "days":               "дней",
        "executor":           "Исполнитель",
        "client":             "Заказчик",
        "value_net":          "Стоимость нетто",
        "value_gross":        "Стоимость брутто",
        "hours_total":        "Всего часов",
        "delivery_time":      "Срок реализации",
        "weeks_6":            "6 нед.",
        "h1_scope":           "1. Объём работ",
        "col_no":             "№",
        "col_item":           "Позиция",
        "col_hours":          "Часы",
        "col_price":          "Цена нетто",
        "total_net":          "ИТОГО НЕТТО",
        "total_gross":        "ИТОГО БРУТТО (НДС 23%)",
        "rate_note":          "Ставка: 250 PLN нетто/час · Все цены нетто, НДС 23%.",
        "free_label":         "бесплатно",
        "h2_license":         "2. Лицензия Bitrix24",
        "license_desc":       "Стоимость лицензии Bitrix24 <strong>не включена</strong> в цену внедрения — Заказчик приобретает её напрямую у Bitrix24. Ниже представлены доступные планы и наша рекомендация для вашей компании.",
        "col_plan":           "План",
        "col_users":          "Пользователи",
        "col_price_mo":       "Цена/мес.",
        "col_features":       "Ключевые функции",
        "rec_prefix":         "Рекомендация для",
        "rec_plan":           "план",
        "prices_note":        "Цены могут измениться — актуальные тарифы на <strong>bitrix24.ru</strong>.",
        "plan_free_feat":     "Базовый CRM, задачи, чат — без автоматизаций и продвинутых отчётов",
        "plan_basic_feat":    "CRM, почта, 24 ГБ диск, базовые автоматизации",
        "plan_std_feat":      "Полный CRM, автоматизации, маркетинг, 100 ГБ диск",
        "plan_pro_feat":      "Всё из Standard + HR, сервисный стол, продвинутая аналитика, 1024 ГБ",
        "plan_ent_feat":      "Полная платформа, несколько филиалов, выделенный сервер, SLA",
        "h3_timeline":        "3. План реализации",
        "week_label":         "Неделя",
        "h4_how":             "4. Как проходит внедрение?",
        "phase_analysis":     "<strong>Анализ</strong> — картируем бизнес-процессы и определяем конфигурацию на онлайн-встрече.",
        "phase_config":       "<strong>Настройка</strong> — настраиваем воронки, автоматизации, поля и права доступа в Bitrix24.",
        "phase_integrations": "<strong>Интеграции</strong> — подключаем телефонию, формы и другие системы.",
        "phase_import":       "<strong>Импорт данных</strong> — переносим контакты, компании и историю из текущих инструментов.",
        "phase_training":     "<strong>Обучение и сдача</strong> — онлайн-обучение команды + сопровождение в первые 2 недели.",
        "h5_terms":           "5. Коммерческие условия",
        "payment":            "Оплата",
        "advance":            "Аванс",
        "delivery":           "Срок реализации",
        "guarantee":          "Гарантия",
        "support":            "Стартовая поддержка",
        "payment_val":        "50% + 50%",
        "delivery_val":       "до 6 недель",
        "guarantee_val":      "12 месяцев",
        "support_val":        "2 недели бесплатно",
        "h6_guarantees":      "6. Наши гарантии",
        "g1_title":           "Выделенный менеджер проекта",
        "g1_text":            "Один PM отвечает за весь проект — полная ответственность и коммуникация.",
        "g2_title":           "Сертифицированные специалисты",
        "g2_text":            "Команда с сертификатами Bitrix24 и многолетним опытом внедрений.",
        "g3_title":           "Фиксированная цена в договоре",
        "g3_text":            "Никаких скрытых расходов. Изменения объёма — только через отдельное дополнение к договору.",
        "h7_accept":          "7. Принятие предложения",
        "accept_text":        "Для принятия предложения просим подписать договор и внести аванс на наш банковский счёт:",
        "contact_label":      "Контакт:",
        "sig_executor":       "Исполнитель",
        "sig_client":         "Заказчик",
        "call_manager_btn":   "Связаться с менеджером",
        "call_manager_sent":  "Ваш запрос передан менеджеру. Он свяжется с вами как можно скорее!",
        "call_manager_error": "Не удалось отправить запрос. Напишите напрямую на info@alphadigital.pl",
    },
}


# ---------------------------------------------------------------------------
# Scope item name translations  (key = Polish name fragment → {lang: name})
# ---------------------------------------------------------------------------

_SCOPE_ITEMS: list[tuple[str, dict[str, str]]] = [
    ("Analiza procesów biznesowych i rejestracja portalu", {
        "en": "Business process analysis & Bitrix24 portal registration",
        "ru": "Анализ бизнес-процессов и регистрация портала Bitrix24",
    }),
    ("Konfiguracja struktury organizacyjnej i kart CRM", {
        "en": "Organizational structure setup & CRM cards (lead, deal, contact, company)",
        "ru": "Настройка организационной структуры и карточек CRM (лид, сделка, контакт, компания)",
    }),
    ("Konfiguracja lejka sprzedażowego", {
        "en": "Sales pipeline configuration (up to 20 stages)",
        "ru": "Настройка воронки продаж (до 20 этапов)",
    }),
    ("Konfiguracja praw dostępu pracowników", {
        "en": "Employee access rights configuration (up to 20 users)",
        "ru": "Настройка прав доступа сотрудников (до 20 пользователей)",
    }),
    ("Automatyzacje i roboty CRM", {
        "en": "CRM automations & robots (up to 5 rules) + document template",
        "ru": "Автоматизации и роботы CRM (до 5 правил) + шаблон документа",
    }),
    ("Import bazy klientów", {
        "en": "Client database import from file (preparation + import)",
        "ru": "Импорт базы клиентов из файла (подготовка + импорт)",
    }),
    ("Podłączenie otwartych linii", {
        "en": "Open channels / messengers connection",
        "ru": "Подключение открытых линий / мессенджеров",
    }),
    ("Integracja z telefonią VoIP", {
        "en": "VoIP telephony integration (Zadarma or other)",
        "ru": "Интеграция с VoIP-телефонией (Zadarma или другая)",
    }),
    ("Integracja formularzy CRM i widżetu ze stroną", {
        "en": "CRM forms & website widget integration",
        "ru": "Интеграция CRM-форм и виджета с сайтом",
    }),
    ("Podłączenie firmowej poczty e-mail", {
        "en": "Corporate email integration (SMTP/IMAP)",
        "ru": "Подключение корпоративной почты (SMTP/IMAP)",
    }),
    ("Integracja z systemami zewnętrznymi", {
        "en": "External system integration (API / webhook)",
        "ru": "Интеграция с внешними системами (API / webhook)",
    }),
    ("Konfiguracja dostępu dla zewnętrznych użytkowników", {
        "en": "External user access configuration (partners/agents)",
        "ru": "Настройка доступа для внешних пользователей (партнёры/агенты)",
    }),
    ("Szkolenie zespołu z obsługi CRM", {
        "en": "Team CRM training (online session)",
        "ru": "Обучение команды работе с CRM (онлайн-сессия)",
    }),
    ("Wsparcie powdrożeniowe przez 2 tygodnie", {
        "en": "Post-implementation support for 2 weeks after handover",
        "ru": "Поствнедренческая поддержка в течение 2 недель после сдачи",
    }),
    ("Podłączenie poczty e-mail", {
        "en": "Email integration (SMTP)",
        "ru": "Подключение почты (SMTP)",
    }),
]


def scope_item(polish_name: str, language: str) -> str:
    """Return translated scope item name, or the original Polish if not found / language is pl."""
    if language == "pl":
        return polish_name
    for fragment, translations in _SCOPE_ITEMS:
        if fragment.lower() in polish_name.lower():
            return translations.get(language, polish_name)
    return polish_name
