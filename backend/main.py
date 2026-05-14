from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import uuid
import json
import logging

from services.company_lookup import lookup_company_by_nip, validate_nip
from services.claude_agent import chat
from services.pdf_generator import generate_proposal_pdf, generate_contract_pdf
from services import session_store
from services.bitrix24 import (
    create_deal_with_contact,
    add_interview_comment,
    add_proposal_comment,
    add_contract_comment,
)
from config import YOUR_COMPANY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AD SelfIntegrator — Generator Ofert")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ── Models ────────────────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    message: str


class SessionResponse(BaseModel):
    session_id: str
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_session(session_id: str) -> dict:
    session = await session_store.load(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesja nie istnieje")
    return session


HOURLY_RATE = 250  # PLN netto per hour


def hours_to_price(hours: float) -> int:
    return round(hours * HOURLY_RATE)


def recommend_license(team_size: int) -> tuple[str, str]:
    if team_size <= 5:
        return "Basic", f"do 5 użytkowników (~229 PLN/mies.) — wystarczający dla {team_size}-osobowego zespołu"
    elif team_size <= 50:
        return "Standard", f"do 50 użytkowników (~459 PLN/mies.) — pełny CRM i automatyzacje dla {team_size}-osobowego zespołu"
    elif team_size <= 100:
        return "Professional", f"do 100 użytkowników (~919 PLN/mies.) — zaawansowana analityka i HR dla {team_size}-osobowego zespołu"
    else:
        return "Enterprise", f"250+ użytkowników (od ~2 299 PLN/mies.) — platforma korporacyjna dla dużego zespołu"


def build_proposal_scope(interview: dict) -> list[dict]:
    """
    Build scope using standard task catalogue (250 PLN/h netto).
    Hours sourced from: "Bitrix24 standard tasks - Final Standard.csv"
    Ranges resolved to mid-point: e.g. 2-10h → 6h.
    """
    team_size = interview.get("team_size", "")
    try:
        size = int("".join(filter(str.isdigit, str(team_size).split()[0])))
    except Exception:
        size = 5

    scope = []

    # ── Analytics & Setup ─────────────────────────────────────────
    # CSV: "Analiza procesów biznesowych firmy" = 5h
    #      "Rejestracja portalu, konsultacje" = 0.5h
    scope.append({
        "item": "Analiza procesów biznesowych i rejestracja portalu Bitrix24",
        "hours": 5.5,
        "price": hours_to_price(5.5),
    })

    # CSV: "Tworzenie struktury firmy i rejestracja pracowników (do 20)" = 1h
    #      "Dostosowanie leadów, dealów, kontaktów, kart firmowych" = 3h
    scope.append({
        "item": "Konfiguracja struktury organizacyjnej i kart CRM (lead, oferta, kontakt, firma)",
        "hours": 4,
        "price": hours_to_price(4),
    })

    # ── Sales pipeline ─────────────────────────────────────────────
    # CSV: "Konfiguracja jednego lejka sprzedaży (do 20 etapów)" = 4h
    scope.append({
        "item": "Konfiguracja lejka sprzedażowego (do 20 etapów)",
        "hours": 4,
        "price": hours_to_price(4),
    })

    # ── Automations ────────────────────────────────────────────────
    automations = interview.get("automations_needed", "")
    if automations and str(automations).strip().lower() not in ("nie", "no", "brak", ""):
        # CSV: "Konfiguracja automatyzacji z wyzwalaczami i robotami (do 5 robotów)" = 3h
        #      "Opracowanie szablonu do automatycznego generowania dokumentów (1 dokument)" = 3h
        scope.append({
            "item": "Automatyzacje i roboty CRM (do 5 reguł) + szablon dokumentu",
            "hours": 6,
            "price": hours_to_price(6),
        })

    # ── Data import ────────────────────────────────────────────────
    current_tools = interview.get("current_tools", "").lower()
    has_data = any(w in current_tools for w in ["excel", "xlsx", "csv", "crm", "baza", "system"])
    if has_data:
        # CSV: "Import bazy klientów z pliku xls" = 2–10h → 6h mid
        scope.append({
            "item": "Import bazy klientów z pliku (przygotowanie + import)",
            "hours": 6,
            "price": hours_to_price(6),
        })

    # ── Integrations ───────────────────────────────────────────────
    if interview.get("telephony_needed"):
        # CSV: "Integracja usługi Zadarma. Proste / robocze scenariusze" = 3–15h → 9h mid
        scope.append({
            "item": "Integracja z telefonią VoIP (Zadarma lub inna)",
            "hours": 9,
            "price": hours_to_price(9),
        })

    integrations = interview.get("integrations", "").lower()
    if any(w in integrations for w in ["formularz", "form", "strona", "www", "website", "landing"]):
        # CSV: "Konfiguracja i integracja formularza CRM (z opracowaniem formularza)" = 2–4h → 3h mid
        #      "Instalacja widżetu na stronie" = 1h
        scope.append({
            "item": "Integracja formularza ze strony internetowej z CRM + widget",
            "hours": 4,
            "price": hours_to_price(4),
        })

    lead_sources = interview.get("lead_sources", "").lower()
    if any(w in lead_sources for w in ["email", "e-mail", "poczta", "mail"]):
        # CSV: "Połączenie pocztowe (SMTP)" = 1h
        scope.append({
            "item": "Podłączenie poczty e-mail (SMTP)",
            "hours": 1,
            "price": hours_to_price(1),
        })

    if any(w in lead_sources for w in ["messenger", "whatsapp", "facebook", "telegram", "chat"]):
        # CSV: "Podłączenie 1 kanału otwartego" = 1h
        scope.append({
            "item": "Podłączenie kanału komunikacji (messenger / chat)",
            "hours": 1,
            "price": hours_to_price(1),
        })

    # ── Access rights ──────────────────────────────────────────────
    if size > 3:
        # CSV: "Konfigurowanie praw dostępu dla pracowników (do 20 użytkowników)" = 2–4h → 3h mid
        scope.append({
            "item": "Konfiguracja praw dostępu pracowników (do 20 użytkowników)",
            "hours": 3,
            "price": hours_to_price(3),
        })

    # ── Training & Support ─────────────────────────────────────────
    # CSV: "Szkolenie w sekcji CRM" = 3–5h → 4h mid
    scope.append({
        "item": "Szkolenie zespołu z obsługi CRM (sesja online)",
        "hours": 4,
        "price": hours_to_price(4),
    })
    # CSV: "Wsparcie po dostarczeniu projektu w ciągu 2 tygodni" = 0h (gratis)
    scope.append({
        "item": "Wsparcie powdrożeniowe przez 2 tygodnie po oddaniu",
        "hours": 0,
        "price": 0,
    })

    return scope


def estimate_timeline(interview: dict) -> list[dict]:
    total_hours = sum(i.get("hours", 0) for i in build_proposal_scope(interview))
    # ~6h productive work per day, 5 days/week
    weeks = max(2, round(total_hours / 30))
    if weeks <= 2:
        return [
            {"week": "1", "phase": "Analiza wymagań, konfiguracja portalu i struktury"},
            {"week": "1–2", "phase": "Lejki, automatyzacje, import danych"},
            {"week": "2", "phase": "Szkolenie i przekazanie projektu"},
        ]
    elif weeks <= 4:
        return [
            {"week": "1", "phase": "Analiza procesów biznesowych i konfiguracja środowiska"},
            {"week": "2", "phase": "Konfiguracja CRM: lejki, karty, pola, automatyzacje"},
            {"week": "3", "phase": "Integracje i import danych"},
            {"week": "4", "phase": "Szkolenia, testy i przekazanie projektu"},
        ]
    else:
        return [
            {"week": "1–2", "phase": "Analiza procesów biznesowych i konfiguracja środowiska"},
            {"week": "2–4", "phase": "Konfiguracja CRM, lejki, automatyzacje, integracje"},
            {"week": "4–5", "phase": "Import danych, testy akceptacyjne, poprawki"},
            {"week": "5–6", "phase": "Szkolenia, przekazanie projektu, wsparcie startowe"},
        ]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/session/start", response_model=SessionResponse)
async def start_session():
    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "state": "collect_user_info",
        "messages": [],
        "user_info": {},
        "company": {},
        "interview": {},
        "proposal_approved": False,
    }

    greeting = (
        "Cześć! Jestem asystentem AI firmy Alpha Digital — pomagam w przygotowaniu "
        "indywidualnej oferty handlowej na integrację systemu Bitrix24.\n\n"
        "Nasza rozmowa będzie przebiegać następująco:\n\n"
        "* najpierw poproszę Cię o podanie **numeru NIP** Twojej firmy, aby znaleźć o niej "
        "informacje w internecie — pomoże mi to przygotować bardziej spersonalizowaną ofertę, "
        "a dane firmy przydadzą się później do sporządzenia umowy;\n"
        "* następnie poproszę Cię o **przedstawienie się**, abym wiedział, z kim rozmawiam;\n"
        "* będę kolejno zadawać pytania o Twoje zadania, wyzwania i potrzeby — możesz "
        "odpowiadać tekstem lub nagrywać **wiadomości głosowe**, jak wygodniej. Na tę część "
        "warto zarezerwować około **30 minut**. Możesz przerwać w dowolnym momencie i wrócić "
        "później, korzystając z linku widocznego powyżej — wszystkie odpowiedzi zostaną "
        "zapisane i wrócimy do miejsca, w którym skończyliśmy;\n"
        "* po udzieleniu odpowiedzi na wszystkie pytania przygotuję **ofertę handlową** na "
        "integrację systemu, w której znajdą się terminy, koszty, proces pracy itd. Będziesz "
        "mógł/mogła ją sprawdzić, coś dodać lub zadać dodatkowe pytania — wprowadzę wszelkie poprawki;\n"
        "* gdy zatwierdzisz ofertę, przygotuję dla Ciebie **umowę** oraz **proformę** do "
        "płatności na rozpoczęcie pracy.\n\n"
        "Zacznijmy! Podaj proszę **numer NIP** swojej firmy."
    )

    session["messages"].append({"role": "assistant", "content": greeting})
    await session_store.save(session_id, session)

    return SessionResponse(session_id=session_id, message=greeting)


@app.get("/api/session/{session_id}")
async def get_session_info(session_id: str):
    """Return session state so the frontend can resume a saved session."""
    session = await get_session(session_id)
    return {
        "session_id": session_id,
        "state": session["state"],
        "messages": session["messages"],
        "proposal_approved": session.get("proposal_approved", False),
    }


@app.post("/api/session/{session_id}/message")
async def send_message(session_id: str, body: MessageRequest):
    session = await get_session(session_id)
    user_msg = body.message.strip()

    if not user_msg:
        raise HTTPException(status_code=400, detail="Wiadomość nie może być pusta")

    session["messages"].append({"role": "user", "content": user_msg})

    claude_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in session["messages"]
        if m["role"] in ("user", "assistant")
    ]

    state_snapshot = {
        "state": session["state"],
        "user_info": session["user_info"],
        "company": session["company"],
        "interview": session["interview"],
    }

    actions = []

    async def tool_executor(tool_call: dict) -> dict | None:
        action = await _handle_tool_call(session, tool_call)
        if action:
            actions.append(action)
        return action

    result = await chat(claude_messages, state_snapshot, tool_executor)

    reply = result["text"]
    if reply:
        session["messages"].append({"role": "assistant", "content": reply})

    await session_store.save(session_id, session)

    return {
        "message": reply,
        "actions": actions,
        "state": session["state"],
    }


async def _handle_tool_call(session: dict, tool_call: dict) -> dict | None:
    name = tool_call["name"]
    inp = tool_call["input"]

    session_id = session["session_id"]

    if name == "submit_user_info":
        session["user_info"] = inp
        nip = inp.get("nip", "").replace("-", "").replace(" ", "")

        if not validate_nip(nip):
            session["messages"].append({
                "role": "assistant",
                "content": "⚠️ Podany numer NIP wydaje się być nieprawidłowy. Czy możesz go sprawdzić i wpisać ponownie?"
            })
            return None

        company = await lookup_company_by_nip(nip)
        if company:
            session["company"] = company
            session["state"] = "confirm_company"
        else:
            session["state"] = "confirm_company"
            session["company"] = {"nip": nip, "name": "Nie znaleziono danych", "address": ""}

        # Create Bitrix24 deal once we have full contact info (second call with first_name)
        if inp.get("first_name") and not session.get("bitrix24_deal_id"):
            deal_id = await create_deal_with_contact(inp, session["company"], session_id)
            if deal_id:
                session["bitrix24_deal_id"] = deal_id
                logger.info("Bitrix24 deal created: %s", deal_id)

        if company:
            return {"type": "company_found", "company": company}
        return {"type": "company_not_found"}

    elif name == "submit_interview_data":
        session["interview"] = inp
        session["state"] = "proposal_ready"

        scope = build_proposal_scope(inp)
        timeline = estimate_timeline(inp)
        total = sum(i["price"] for i in scope)

        try:
            size = int("".join(filter(str.isdigit, str(inp.get("team_size", "5")).split()[0])))
        except Exception:
            size = 5
        license_plan, license_reason = recommend_license(size)

        session["proposal_data"] = {
            "scope": scope,
            "timeline": timeline,
            "total_net": total,
            "total_gross": round(total * 1.23),
            "validity_days": 30,
            "your_company": YOUR_COMPANY,
            "license_plan": license_plan,
            "license_reason": license_reason,
        }

        # Enrich Bitrix24 deal: Q&A comment + proposal link
        deal_id = session.get("bitrix24_deal_id")
        if deal_id:
            await add_interview_comment(deal_id, inp)
            await add_proposal_comment(deal_id, session_id, total, round(total * 1.23))

        return {"type": "proposal_ready"}

    elif name == "update_proposal_data":
        if "updated_fields" in inp:
            session["proposal_data"].update(inp["updated_fields"])
        return {"type": "proposal_updated"}

    elif name == "approve_proposal":
        if inp.get("confirmed"):
            session["proposal_approved"] = True
            session["state"] = "contract_ready"

            # Add contract link to Bitrix24
            deal_id = session.get("bitrix24_deal_id")
            if deal_id:
                await add_contract_comment(deal_id, session_id)

            return {"type": "contract_ready"}

    return None


@app.get("/api/session/{session_id}/proposal.pdf")
async def download_proposal(session_id: str):
    session = await get_session(session_id)
    if session["state"] not in ("proposal_ready", "revisions", "contract_ready"):
        raise HTTPException(status_code=400, detail="Oferta nie jest jeszcze gotowa")

    data = {
        **session.get("proposal_data", {}),
        "user_info": session["user_info"],
        "company": session["company"],
        "interview": session["interview"],
        "session_id": session_id,
    }
    html_bytes = generate_proposal_pdf(data)
    return Response(content=html_bytes, media_type="text/html; charset=utf-8")


@app.get("/api/session/{session_id}/contract.pdf")
async def download_contract(session_id: str):
    session = await get_session(session_id)
    if not session.get("proposal_approved"):
        raise HTTPException(status_code=400, detail="Oferta nie została jeszcze zatwierdzona")

    data = {
        **session.get("proposal_data", {}),
        "user_info": session["user_info"],
        "company": session["company"],
        "interview": session["interview"],
        "session_id": session_id,
    }
    html_bytes = generate_contract_pdf(data)
    return Response(content=html_bytes, media_type="text/html; charset=utf-8")


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
