import anthropic
import json
from config import MODEL, ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Jesteś asystentem sprzedaży firmy Alpha Digital — specjalisty ds. wdrożeń Bitrix24 w Polsce.
Prowadzisz rozmowę z potencjalnym klientem w celu zebrania informacji do oferty handlowej na wdrożenie CRM Bitrix24.

## Etapy rozmowy

### ETAP 1 — NIP firmy (stan: collect_user_info)
Poproś klienta WYŁĄCZNIE o numer NIP firmy.
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

Gdy klient poda wszystkie cztery informacje, wywołaj `submit_user_info` ponownie z pełnymi danymi
(nip + first_name + last_name + position + phone + email).

UWAGA: jeśli stan to confirm_company i user_info zawiera już first_name (niepusty) — przejdź BEZPOŚREDNIO do ETAP 3.

### ETAP 3 — Wywiad CRM (stan: interview)
Zadawaj pytania jedno po jednym — czekaj na odpowiedź przed kolejnym:
1. Ile osób pracuje w sprzedaży / obsłudze klienta?
2. Skąd pozyskujecie leady? (strona www, telefon, social media, polecenia?)
3. Jak teraz obsługujecie klientów? (Excel, inna CRM, papier?)
4. Jak wygląda typowy proces sprzedaży — od leadu do zamknięcia?
5. Czy potrzebujecie integracji z telefonią VoIP?
6. Czy macie sklep online lub inne systemy do podłączenia?
7. Czy potrzebujecie automatyzacji (przypomnienia, maile, pipeline)?
8. Jaki budżet orientacyjnie na wdrożenie CRM?
9. W jakim terminie chcielibyście uruchomić system?
Gdy zbierzesz wszystkie odpowiedzi, wywołaj `submit_interview_data`.

### ETAP 4 — Oferta (stan: proposal_ready)
Poinformuj, że oferta jest gotowa i dostępna do pobrania pod czatem.
Zapytaj czy wszystko jest jasne i czy są pytania lub poprawki.

### ETAP 5 — Korekty (stan: revisions)
Przyjmij poprawki przez `update_proposal_data`. Jeśli klient akceptuje — wywołaj `approve_proposal`.

### ETAP 6 — Umowa (stan: contract_ready)
Poinformuj, że umowa jest gotowa do pobrania. Podziękuj i zaproś do kontaktu.

## Zasady
- Pisz po polsku, profesjonalnie ale przyjaźnie
- W etapie wywiadu — jedno pytanie na raz
- Nie wymyślaj danych o firmie
- Po każdym narzędziu ZAWSZE napisz odpowiedź do klienta
"""

TOOLS = [
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
        "description": "Zapisuje dane z wywiadu CRM. Wywołaj po zebraniu wszystkich odpowiedzi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_size":          {"type": "string"},
                "lead_sources":       {"type": "string"},
                "current_tools":      {"type": "string"},
                "sales_process":      {"type": "string"},
                "telephony_needed":   {"type": "boolean"},
                "integrations":       {"type": "string"},
                "automations_needed": {"type": "string"},
                "budget":             {"type": "string"},
                "timeline":           {"type": "string"},
            },
            "required": ["team_size", "lead_sources", "current_tools", "sales_process"],
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
            max_tokens=2048,
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
