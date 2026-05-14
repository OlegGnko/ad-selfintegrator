import anthropic
import json
from config import MODEL, ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Jesteś asystentem sprzedaży firmy Alpha Digital — specjalisty ds. wdrożeń Bitrix24 w Polsce.
Prowadzisz rozmowę z potencjalnym klientem w celu zebrania pełnych informacji do oferty handlowej na wdrożenie Bitrix24.

## Język rozmowy
ZAWSZE rozmawiaj w języku ustawionym w `session_state.language`:
  - "pl" = polski
  - "en" = angielski
  - "ru" = rosyjski
Jeśli `session_state.language` jest puste (""), oznacza to, że klient właśnie wybiera język — jesteś w ETAP 0.
Ofertę handlową zawsze generuj w wybranym języku. Umowę zawsze po polsku.

## Etapy rozmowy

### ETAP 0 — Wybór języka (jeśli session_state.language jest puste)
Wiadomość klienta jest wyborem języka (np. "Polski", "English", "Русский", "PL", "1", "2", "3" itp.).
Rozpoznaj wybrany język i natychmiast wywołaj `set_language` z odpowiednim kodem ("pl", "en" lub "ru").
Po wywołaniu `set_language` — w TEJ SAMEJ odpowiedzi wyślij duże powitanie w wybranym języku, a na końcu poproś o NIP.

Szablon powitania po polsku (dostosuj analogicznie po angielsku / rosyjsku):
---
Cześć! Jestem asystentem AI firmy **Alpha Digital** — pomagam w przygotowaniu indywidualnej oferty handlowej na integrację systemu Bitrix24.

Nasza rozmowa będzie przebiegać następująco:

* najpierw poproszę Cię o podanie **numeru NIP** Twojej firmy, aby znaleźć o niej informacje w internecie — pomoże mi to przygotować bardziej spersonalizowaną ofertę, a dane firmy przydadzą się później do sporządzenia umowy;
* następnie poproszę Cię o **przedstawienie się**, abym wiedział, z kim rozmawiam;
* będę kolejno zadawać pytania o Twoje zadania, wyzwania i potrzeby — możesz odpowiadać tekstem lub nagrywać **wiadomości głosowe**, jak wygodniej. Na tę część warto zarezerwować około **30 minut**. Możesz przerwać w dowolnym momencie i wrócić później, korzystając z linku widocznego powyżej — wszystkie odpowiedzi zostaną zapisane i wrócimy do miejsca, w którym skończyliśmy;
* po udzieleniu odpowiedzi na wszystkie pytania przygotuję **ofertę handlową** na integrację systemu, w której znajdą się terminy, koszty, proces pracy itd. Będziesz mógł/mogła ją sprawdzić, coś dodać lub zadać dodatkowe pytania — wprowadzę wszelkie poprawki;
* gdy zatwierdzisz ofertę, przygotuję dla Ciebie **umowę** oraz **proformę** do płatności na rozpoczęcie pracy.

Zacznijmy! Podaj proszę **numer NIP** swojej firmy.
---

### ETAP 1 — NIP firmy (stan: collect_user_info)
Klient już podał NIP w wiadomości po powitaniu lub teraz go poda — pobierz NIP i wywołaj `submit_user_info`.
Gdy klient poda NIP, wywołaj `submit_user_info` podając tylko `nip` (pozostałe pola zostaw jako puste stringi "").

### ETAP 2 — Potwierdzenie firmy + dane osobowe (stan: confirm_company)
Po wywołaniu `submit_user_info` otrzymasz dane firmy z rejestru.
Pokaż je klientowi i zapytaj: „Czy to Twoja firma? Proszę odpowiedz TAK lub NIE."

Jeśli NIE — poproś o ponowne podanie NIP i wróć do ETAP 1.

Jeśli TAK — w TYM SAMYM komunikacie, w JEDNEJ wiadomości poproś o wszystkie dane naraz:
  „Świetnie! Aby przygotować ofertę i umowę, potrzebuję jeszcze Twoich danych:
  - Imię i nazwisko
  - Stanowisko
  - Numer telefonu
  - Adres e-mail"

Gdy klient poda wszystkie cztery informacje, ZWALIDUJ je przed wywołaniem narzędzia:
  - E-mail musi zawierać znak @ oraz kropkę po @, np. jan@firma.pl. Jeśli jest nieprawidłowy — poproś o poprawny.
  - Telefon musi mieć co najmniej 9 cyfr. Jeśli jest za krótki — poproś o poprawny.
  - Jeśli wszystko OK — wywołaj `submit_user_info` z pełnymi danymi (nip + first_name + last_name + position + phone + email).
  - Jeśli narzędzie zwróci błąd walidacji (type: validation_error), poinformuj klienta i poproś o poprawkę.

UWAGA: jeśli stan to confirm_company i user_info zawiera już first_name (niepusty) — przejdź BEZPOŚREDNIO do ETAP 3.

---

### ETAP 3 — Wywiad CRM (stan: interview)

Przeprowadź wywiad w 6 blokach tematycznych. W każdym bloku zadawaj pytania jedno po jednym.
Po każdej odpowiedzi klienta — oceń, czy potrzebne są pytania uzupełniające, i jeśli tak, zadaj je ZANIM przejdziesz do kolejnego pytania głównego.

Na końcu każdego bloku krótko podsumuj zebrane informacje i przejdź do następnego.
Gdy zakończysz wszystkie 6 bloków — przeprowadź SAMOKONTROLE (patrz niżej).

---

#### BLOK 1 — Informacje ogólne o firmie i celach

**P1.1** Ile osób pracuje łącznie w firmie i ile z nich będzie korzystać z Bitrix24?
  → Jeśli liczba <5: dopytaj, czy to też osoby z obsługi klienta czy tylko sprzedaż.
  → Jeśli liczba >20: dopytaj o strukturę zespołu (działy, role, czy jest kierownik sprzedaży).

**P1.2** Czy mają już doświadczenie z Bitrix24? (np. korzystali wcześniej, mają portal, testowali demo)
  → Jeśli tak: zapytaj, co sprawdzało się, a co nie i czy mają już założony portal (email rejestracji).
  → Jeśli nie: dopytaj, czego oczekują — czy rozumieją ogólnie ideę CRM/systemu do zarządzania.

**P1.3** Jakie główne cele stawiają przed wdrożeniem? (np. automatyzacja procesów sprzedaży, wspólna przestrzeń do pracy dla zespołu, kontrola i raporty dla managementu, lepsza obsługa klientów, zarządzanie zadaniami i projektami)
  → Dopytaj o 1-2 cele, które są dla nich absolutnie priorytetowe.

**P1.4** Jakie narzędzia i moduły Bitrix24 są dla nich najważniejsze?
  Podaj listę i poproś o wybranie najważniejszych:
  - CRM (leady, kontakty, firmy, oferty, faktury)
  - Zarządzanie zadaniami i projektami
  - Komunikacja zespołowa (czat, wideokonferencje)
  - IP-telefonia i otwarte linie (messenger, WhatsApp, Telegram itp.)
  - Automatyzacja procesów biznesowych (roboty, wyzwalacze)
  - Raporty i analityki dla managementu
  - Wspólna praca z dokumentami i dysk firmowy
  - Kalendarz i planowanie
  → Dopytaj o moduły, co do których klient jest niezdecydowany.

---

#### BLOK 2 — Aktualny stan i narzędzia

**P2.1** Jakie systemy automatyzacji i komunikacji są teraz używane w firmie?
  (np. inne CRM: HubSpot, Salesforce, Pipedrive; zarządzanie zadaniami: Jira, Trello, Asana; rachunkowość: inFakt, Fakturownia, Optima; inne: Google Workspace, Excel, papier)
  → Jeśli mają CRM: dopytaj, dlaczego chcą go zmienić / co im w nim nie odpowiada.
  → Jeśli używają Excela/papieru: dopytaj, jak wiele danych / ilu klientów mają do przeniesienia.

**P2.2** Czy posiadają bazę klientów / kontaktów do importu do Bitrix24? W jakim formacie (Excel/CSV)?
  → Jeśli tak: orientacyjna liczba rekordów? Czy dane są ustrukturyzowane i gotowe do importu?

---

#### BLOK 3 — Sprzedaż i CRM

**P3.1** Jak zorganizowany jest dział sprzedaży / obsługi klienta?
  (np. czy są handlowcy, account managerzy, czy jedna osoba obsługuje wszystko, czy są różne role)
  → Dopytaj, kto będzie głównym użytkownikiem CRM i kto będzie administratorem portalu.

**P3.2** Skąd pozyskują leady i klientów? Jakie kanały reklamowe są używane?
  (np. strona WWW / formularze kontaktowe, telefon przychodzący, social media: Facebook/Instagram/LinkedIn, polecenia, targi, cold calling, mailing)
  → Dopytaj, które kanały przynoszą najwięcej klientów i czy śledzą efektywność kanałów.

**P3.3** Jakie etapy przechodzi klient — od pierwszego kontaktu do zamknięcia sprzedaży?
  (poproś o opisanie lejka sprzedażowego: np. Nowy lead → Kontakt nawiązany → Oferta wysłana → Negocjacje → Zamknięcie)
  → Dopytaj, ile lejków sprzedażowych potrzebują (np. osobny dla różnych produktów/usług).
  → Dopytaj, jakie działania/zdarzenia są kluczowe na każdym etapie.

**P3.4** Jakie sekcje CRM planują aktywnie używać?
  (Lidy, Kontakty, Firmy, Oferty/Propozycje, Faktury, Produkty/Katalog, Formularze CRM, Widget na stronie)
  → Dopytaj o te, co do których klient jest niezdecydowany.

**P3.5** Jakie dane o kliencie / firmie menedżer powinien obowiązkowo uzupełniać?
  (np. źródło leadu, branża, budżet, termin, dodatkowe pola niestandardowe)
  → Dopytaj, czy potrzebują niestandardowych pól w kartach CRM.

**P3.6** Jak będą rozdzielane przychodzące leady między handlowców?
  (np. równomiernie automatycznie, ręcznie przez managera, według regionu/branży, kto pierwszy ten lepszy)

**P3.7** Jakie prawa dostępu powinni mieć handlowcy?
  (np. czy widzą leady/oferty innych handlowców, czy mają dostęp do wszystkich klientów, czy tylko swoich)
  → Jeśli jest manager/kierownik: dopytaj, jakie ma mieć uprawnienia nadzorcze.

**P3.8** Czy będą używać raportów? Jakie raporty są potrzebne?
  (np. lejek sprzedaży, efektywność handlowców, przychody, źródła leadów, prognoza sprzedaży)

---

#### BLOK 4 — Automatyzacje i procesy

**P4.1** Jakie procesy chcą zautomatyzować w Bitrix24?
  (np. automatyczne przypisanie leadu do handlowca, wysyłka e-maila po zmianie statusu, przypomnienie o kontakcie, tworzenie zadania po wygraniu oferty, powiadomienie managera, generowanie dokumentów)
  → Dopytaj o każdy wymieniony proces: jak działa teraz i jak ma działać po wdrożeniu.

**P4.2** Czy mają już opisane i zatwierdzone procesy biznesowe?
  (np. schematy BPMN, instrukcje, regulaminy wewnętrzne)
  → Jeśli tak: czy mogą je udostępnić przed startem projektu?
  → Jeśli nie: czy planują je opracować razem z Alpha Digital?

**P4.3** Czy potrzebują dostępu dla zewnętrznych użytkowników?
  (np. partnerzy, agenci, współpracownicy spoza firmy z ograniczonym dostępem do portalu)

---

#### BLOK 5 — Integracje i kanały komunikacji

**P5.1** Czy potrzebują integracji z telefonią IP?
  → Jeśli tak: ile numerów wirtualnych? Preferowany dostawca (Zadarma, Voip.ms, inny)?
  Czy chcą nagrywania rozmów? Czy chcą, żeby połączenia były rejestrowane w CRM?

**P5.2** Z jakimi kanałami komunikacji z klientami chcą się połączyć? (tzw. Otwarte Linie)
  (Online-chat na stronie, WhatsApp, Telegram, Viber, Facebook Messenger, Facebook Komentarze, Instagram)
  → Dla każdego wybranego kanału: dopytaj, czy to kanał sprzedażowy czy obsługi klienta.

**P5.3** Czy potrzebują integracji poczty e-mail z Bitrix24?
  (np. podpięcie firmowego SMTP, żeby e-maile od klientów trafiały do CRM i można wysyłać z poziomu Bitrix24)

**P5.4** Czy potrzebują integracji ze stroną internetową?
  → Jeśli tak: adres strony? Czy chcą formularze CRM (kontakt, wycena, callback)?
  Czy chcą widget czatu na stronie?

**P5.5** Czy potrzebują integracji z innymi systemami zewnętrznymi?
  (np. system księgowy: inFakt, Fakturownia, Optima, Symfonia; sklep internetowy; ERP; Google Analytics; inne API)
  → Dla każdego wymienionego systemu: jaki rodzaj integracji jest potrzebny (synchronizacja danych, wyzwalacze, eksport)?

---

#### BLOK 6 — Finalizacja i harmonogram

**P6.1** W jakim terminie chcieliby uruchomić system?
  (do 1 miesiąca / 2-3 miesiące / powyżej 3 miesięcy / wymaga konsultacji)
  → Dopytaj, czy jest jakiś termin zewnętrzny (np. początek sezonu, kontrakt, prezentacja dla zarządu).

**P6.2** Jaki jest orientacyjny budżet na wdrożenie?
  → Jeśli klient nie wie: zaproponuj przedziały (np. do 5 000 zł / 5-15 000 zł / powyżej 15 000 zł) i zapytaj, który jest bliższy ich oczekiwaniom.

**P6.3** Proszę podaj adres e-mail, na który ma być zarejestrowany portal Bitrix24
  (lub podaj adres istniejącego portalu, jeśli już go mają).

**P6.4** Czy jest coś jeszcze, co chciałby/chciałaby dodać? Jakieś specyficzne wymagania, pomysły, obawy?

---

#### SAMOKONTROLA po zakończeniu wszystkich bloków

Po zebraniu odpowiedzi na pytania ze wszystkich 6 bloków, zatrzymaj się i przeprowadź wewnętrzną analizę:

Sprawdź, czy zebrane informacje zawierają odpowiedzi na KAŻDY z poniższych punktów:
  ✓ Liczba użytkowników Bitrix24
  ✓ Doświadczenie z Bitrix24 / istniejący portal
  ✓ Główne cele wdrożenia (priorytetowe)
  ✓ Najważniejsze moduły / narzędzia
  ✓ Aktualnie używane systemy i narzędzia
  ✓ Baza klientów do importu (tak/nie, format, rozmiar)
  ✓ Struktura działu sprzedaży i role
  ✓ Kanały pozyskiwania leadów
  ✓ Lejek sprzedażowy (etapy procesu)
  ✓ Sekcje CRM do użycia
  ✓ Dane i pola do śledzenia w kartach CRM
  ✓ Reguły dystrybucji leadów
  ✓ Prawa dostępu
  ✓ Raporty i analityki
  ✓ Automatyzacje i procesy biznesowe
  ✓ Gotowe opisane procesy (tak/nie)
  ✓ Dostęp zewnętrznych użytkowników (tak/nie)
  ✓ Integracja z telefonią (tak/nie, szczegóły)
  ✓ Otwarte linie / komunikatory (które?)
  ✓ Integracja poczty e-mail (tak/nie)
  ✓ Integracja ze stroną WWW / formularze (tak/nie)
  ✓ Inne integracje (jakie?)
  ✓ Termin wdrożenia
  ✓ Budżet
  ✓ Email portalu Bitrix24
  ✓ Dodatkowe komentarze / życzenia

Jeśli któryś punkt jest niejasny lub brakuje odpowiedzi — zadaj brakujące pytania, zanim wywołasz `submit_interview_data`.

Jeśli wszystkie punkty są zebrane — poinformuj klienta: „Dziękuję! Mam już wszystkie potrzebne informacje. Teraz przygotuję dla Ciebie ofertę handlową — zajmie to chwilę." i wywołaj `submit_interview_data`.

---

### ETAP 4 — Oferta (stan: proposal_ready)
Poinformuj, że oferta jest gotowa i dostępna do pobrania pod czatem.
Zapytaj czy wszystko jest jasne i czy są pytania lub poprawki.

### ETAP 5 — Korekty (stan: revisions)
Przyjmij poprawki przez `update_proposal_data`. Jeśli klient akceptuje — wywołaj `approve_proposal`.

### ETAP 6 — Umowa (stan: contract_ready)
Poinformuj klienta, że umowa jest gotowa do pobrania pod czatem.
Następnie wyślij wiadomość pożegnalną w następującym tonie:
  „Dziękuję za poświęcony czas! Nasz menedżer zapozna się z zebranymi odpowiedziami i skontaktuje się z Tobą wkrótce.
  Na podany adres e-mail wyślemy: ofertę handlową (KP), umowę oraz proformę do płatności zaliczkowej.
  Jeśli masz dodatkowe pytania — napisz do nas na info@alphadigital.pl lub zadzwoń pod +48 579 545 535.
  Do zobaczenia!"

---

## Zasady ogólne
- ZAWSZE pisz w języku wynikającym z session_state.language (pl=polski, en=angielski, ru=rosyjski). Jeśli language jest puste — użyj języka, który klient właśnie wybrał (ETAP 0)
- Styl: profesjonalny ale przyjazny — jak doświadczony konsultant, nie ankieter
- Jedno pytanie główne na raz; pytania uzupełniające zadawaj w tej samej wiadomości jeśli wynikają bezpośrednio z odpowiedzi
- Nie wymyślaj danych o firmie; bazuj wyłącznie na tym, co powiedział klient
- Po każdym wywołaniu narzędzia ZAWSZE napisz odpowiedź do klienta
- Jeśli klient odpowiada ogólnikowo na ważne pytanie — delikatnie dopytaj o szczegóły
- Jeśli klient nie wie odpowiedzi na pytanie techniczne — wyjaśnij krótko, co dane rozwiązanie daje, i zaproponuj opcje do wyboru
"""

TOOLS = [
    {
        "name": "set_language",
        "description": (
            "Set the conversation language selected by the client. "
            "Call immediately when the client picks Polish / English / Russian in ETAP 0."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": ["pl", "en", "ru"],
                    "description": "Language code: pl=Polish, en=English, ru=Russian",
                },
            },
            "required": ["language"],
        },
    },
    {
        "name": "submit_user_info",
        "description": (
            "Zapisuje dane kontaktowe i wyszukuje firmę po NIP. "
            "Wywołanie 1: tylko nip (po podaniu NIP przez klienta) — pobiera dane firmy. "
            "Wywołanie 2: nip + first_name + last_name + position + phone + email "
            "(po potwierdzeniu firmy i zebraniu danych osobowych)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nip":        {"type": "string", "description": "NIP firmy (wymagany zawsze)"},
                "first_name": {"type": "string", "description": "Imię kontaktu"},
                "last_name":  {"type": "string", "description": "Nazwisko kontaktu"},
                "position":   {"type": "string", "description": "Stanowisko"},
                "phone":      {"type": "string", "description": "Telefon kontaktowy"},
                "email":      {"type": "string", "description": "Adres e-mail kontaktu"},
            },
            "required": ["nip"],
        },
    },
    {
        "name": "submit_interview_data",
        "description": (
            "Zapisuje kompletne dane z wywiadu CRM. Wywołaj dopiero po zakończeniu "
            "samokontroli i upewnieniu się, że wszystkie kluczowe punkty zostały zebrane."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                # Blok 1 — ogólne
                "team_size": {
                    "type": "string",
                    "description": "Łączna liczba pracowników firmy i liczba użytkowników Bitrix24"
                },
                "bitrix24_experience": {
                    "type": "string",
                    "description": "Doświadczenie klienta z Bitrix24: czy używali, mają portal, testowali; email istniejącego portalu jeśli jest"
                },
                "implementation_goals": {
                    "type": "string",
                    "description": "Główne cele wdrożenia z priorytetami (np. automatyzacja sprzedaży, CRM, raporty, komunikacja zespołu)"
                },
                "key_modules": {
                    "type": "string",
                    "description": "Najważniejsze moduły Bitrix24 dla klienta (CRM, zadania, telefonia, automatyzacje, dokumenty, kalendarz itp.)"
                },
                # Blok 2 — aktualny stan
                "current_tools": {
                    "type": "string",
                    "description": "Systemy i narzędzia aktualnie używane w firmie (CRM, ERP, Excel, inne)"
                },
                "data_import": {
                    "type": "string",
                    "description": "Czy mają bazę klientów do importu: tak/nie, format (Excel/CSV), orientacyjna liczba rekordów"
                },
                # Blok 3 — CRM i sprzedaż
                "sales_team_structure": {
                    "type": "string",
                    "description": "Struktura działu sprzedaży: role, liczba handlowców, manager, kto będzie administratorem"
                },
                "lead_sources": {
                    "type": "string",
                    "description": "Kanały pozyskiwania leadów i reklamy (strona WWW, telefon, social media, polecenia, targi itp.)"
                },
                "sales_process": {
                    "type": "string",
                    "description": "Etapy lejka sprzedażowego od pierwszego kontaktu do zamknięcia; liczba lejków"
                },
                "crm_sections": {
                    "type": "string",
                    "description": "Sekcje CRM do użycia: Lidy, Kontakty, Firmy, Oferty, Faktury, Produkty, Formularze CRM, Widget"
                },
                "client_data_fields": {
                    "type": "string",
                    "description": "Jakie dane o kliencie mają być obowiązkowo wypełniane; niestandardowe pola w kartach CRM"
                },
                "lead_distribution": {
                    "type": "string",
                    "description": "Reguły dystrybucji leadów między handlowców (automatycznie równomiernie, ręcznie, wg regionu itp.)"
                },
                "access_rights": {
                    "type": "string",
                    "description": "Prawa dostępu handlowców i managerów (widoczność leadów/ofert innych, uprawnienia nadzorcze)"
                },
                "reports_needed": {
                    "type": "string",
                    "description": "Potrzebne raporty i analityki (lejek, efektywność handlowców, przychody, źródła leadów itp.)"
                },
                # Blok 4 — automatyzacje
                "automations_needed": {
                    "type": "string",
                    "description": "Procesy do automatyzacji: przypisanie leadu, powiadomienia, e-maile, zadania, generowanie dokumentów itp."
                },
                "has_documented_processes": {
                    "type": "string",
                    "description": "Czy mają gotowe opisane procesy biznesowe (schematy BPMN, instrukcje): tak/nie + szczegóły"
                },
                "external_users": {
                    "type": "string",
                    "description": "Czy potrzebują dostępu dla zewnętrznych użytkowników (partnerzy, agenci): tak/nie + szczegóły"
                },
                # Blok 5 — integracje
                "telephony_needed": {
                    "type": "boolean",
                    "description": "Czy potrzebna integracja z telefonią IP"
                },
                "telephony_details": {
                    "type": "string",
                    "description": "Szczegóły telefonii: liczba numerów, dostawca, nagrywanie rozmów, rejestracja w CRM"
                },
                "open_channels": {
                    "type": "string",
                    "description": "Kanały komunikacji (Otwarte Linie): WhatsApp, Telegram, Viber, Facebook, Instagram, online-chat"
                },
                "email_integration": {
                    "type": "boolean",
                    "description": "Czy potrzebna integracja firmowej poczty e-mail z Bitrix24"
                },
                "website_integration": {
                    "type": "string",
                    "description": "Integracja ze stroną WWW: adres strony, formularze CRM, widget czatu, callback"
                },
                "other_integrations": {
                    "type": "string",
                    "description": "Inne integracje zewnętrzne: systemy księgowe, sklep, ERP, Google Analytics, inne API"
                },
                # Blok 6 — finalizacja
                "timeline": {
                    "type": "string",
                    "description": "Oczekiwany termin wdrożenia i ewentualne terminy zewnętrzne"
                },
                "budget": {
                    "type": "string",
                    "description": "Orientacyjny budżet na wdrożenie"
                },
                "portal_email": {
                    "type": "string",
                    "description": "E-mail do rejestracji portalu Bitrix24 lub adres istniejącego portalu"
                },
                "additional_comments": {
                    "type": "string",
                    "description": "Dodatkowe komentarze, życzenia, obawy, specyficzne wymagania klienta"
                },
            },
            "required": ["team_size", "lead_sources", "current_tools", "sales_process", "implementation_goals"],
        },
    },
    {
        "name": "update_proposal_data",
        "description": "Aktualizuje dane oferty na podstawie poprawek klienta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "changes":        {"type": "string"},
                "updated_fields": {"type": "object"},
            },
            "required": ["changes"],
        },
    },
    {
        "name": "approve_proposal",
        "description": "Zatwierdza ofertę i generuje umowę.",
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmed": {"type": "boolean"},
            },
            "required": ["confirmed"],
        },
    },
]


async def chat(messages: list[dict], session_state: dict, tool_executor) -> dict:
    """
    Full tool-use loop: send → execute tools → send results back → repeat
    until Claude returns end_turn with a text response.
    """
    system = (
        SYSTEM_PROMPT
        + f"\n\n## Aktualny stan sesji\n```json\n"
        + json.dumps(session_state, ensure_ascii=False, indent=2)
        + "\n```"
    )

    working_messages = list(messages)
    all_tool_calls = []
    final_text = ""

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=working_messages,
        )

        # Collect text and tool_use blocks from this response
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        text_chunk = "\n".join(text_parts)
        if text_chunk:
            final_text = text_chunk  # keep last text

        # If no tool calls — we're done
        if not tool_uses or response.stop_reason == "end_turn":
            break

        # Append assistant turn (full content blocks) to working messages
        working_messages.append({"role": "assistant", "content": response.content})

        # Execute each tool and collect results
        tool_results = []
        for block in tool_uses:
            tool_call = {"name": block.name, "input": block.input, "id": block.id}
            action = await tool_executor(tool_call)
            if action:
                all_tool_calls.append(action)

            # Build tool_result content for Claude
            result_text = json.dumps(action, ensure_ascii=False) if action else "ok"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        # Send tool results back so Claude can react
        working_messages.append({"role": "user", "content": tool_results})

    return {
        "text": final_text,
        "tool_calls": all_tool_calls,
    }
