"""
Bitrix24 CRM integration via inbound webhook.

Flow -> Bitrix24 pipeline stages (category 53):
  1. submit_user_info (full data)  -> create Contact + Company + Deal  [Nowy]
  2. submit_interview_data         -> Q&A comment + proposal file       [Odpowiedzi -> Oferta]
  3. approve_proposal              -> contract file                     [Umowa]

Stages auto-detected from crm.dealcategory.stage.list by position index:
  index 0 -> deal created    (Nowy)
  index 1 -> interview done  (Odpowiedzi)
  index 2 -> proposal ready  (Oferta)
  index 3 -> contract ready  (Umowa)

File fields in deal category 53 (section Dokumenty):
  FIELD_OFERTA  UF_CRM_1778757181337
  FIELD_UMOWA   UF_CRM_1778757195020
"""

import base64
import logging

import httpx

from config import APP_BASE_URL, BITRIX24_PIPELINE_ID, BITRIX24_STAGE_ID, BITRIX24_WEBHOOK_URL

logger = logging.getLogger(__name__)

DEAL_ENTITY_TYPE = 2  # Bitrix24 numeric entity type for CRM Deal

# File-type field IDs in deal category 53 (section "Dokumenty")
FIELD_OFERTA = "UF_CRM_1778757181337"
FIELD_UMOWA  = "UF_CRM_1778757195020"

# Cache stages list so we don't hit API on every request
_stages_cache: list[str] = []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _bx(method: str, params: dict) -> dict:
    """POST a single Bitrix24 REST call. Returns response dict or {}."""
    if not BITRIX24_WEBHOOK_URL:
        return {}
    url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{method}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=params)
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        logger.warning("Bitrix24 %s failed: %s", method, exc)
        return {}


async def _get_stages() -> list[str]:
    """Return ordered list of STATUS_IDs for the configured pipeline (work stages only)."""
    global _stages_cache
    if _stages_cache:
        return _stages_cache

    cat_id = int(BITRIX24_PIPELINE_ID or 0)
    if cat_id == 0:
        _stages_cache = ["NEW", "PREPARATION", "PREPAYMENT_INVOIC", "EXECUTING", "FINAL_INVOICE"]
        return _stages_cache

    result = await _bx("crm.dealcategory.stage.list", {"id": cat_id})
    raw = result.get("result", [])
    raw.sort(key=lambda s: int(s.get("SORT", 0)))
    skip = {f"C{cat_id}:WON", f"C{cat_id}:LOSE", f"C{cat_id}:APOLOGY"}
    work = [s["STATUS_ID"] for s in raw if s["STATUS_ID"] not in skip]
    _stages_cache = work or [f"C{cat_id}:NEW"]
    logger.info("Bitrix24 pipeline %s stages: %s", cat_id, _stages_cache)
    return _stages_cache


async def _stage(index: int) -> str:
    """Return STATUS_ID at given index (clamped to last stage)."""
    if BITRIX24_STAGE_ID and index == 0:
        return BITRIX24_STAGE_ID
    stages = await _get_stages()
    return stages[min(index, len(stages) - 1)]


async def _move_deal(deal_id: str, stage_index: int) -> None:
    """Advance deal to stage at given index."""
    stage_id = await _stage(stage_index)
    await _bx("crm.deal.update", {"id": int(deal_id), "fields": {"STAGE_ID": stage_id}})
    logger.info("Bitrix24: deal %s -> stage[%d] %s", deal_id, stage_index, stage_id)


async def _attach_file(deal_id: str, field_id: str, filename: str, content: bytes) -> None:
    """
    Attach a file to a file-type custom field on a deal via base64 inline upload.
    Bitrix24 format: { field_id: {"fileData": ["filename", "base64content"]} }
    """
    b64 = base64.b64encode(content).decode("utf-8")
    result = await _bx("crm.deal.update", {
        "id": int(deal_id),
        "fields": {field_id: {"fileData": [filename, b64]}},
    })
    logger.info("Bitrix24: attached %s to deal %s field %s (ok=%s)",
                filename, deal_id, field_id, result.get("result"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_deal_with_contact(
    user_info: dict, company: dict, session_id: str
) -> str | None:
    """
    Create a Bitrix24 Contact, Company and Deal linked together.
    Deal starts at stage index 0 (Nowy).
    Returns deal ID as string, or None if integration is disabled.
    """
    if not BITRIX24_WEBHOOK_URL:
        return None

    # 1. Contact
    phone_val = user_info.get("phone", "")
    email_val = user_info.get("email", "")
    contact_res = await _bx("crm.contact.add", {"fields": {
        "NAME":      user_info.get("first_name", ""),
        "LAST_NAME": user_info.get("last_name", ""),
        "POST":      user_info.get("position", ""),
        "PHONE": [{"VALUE": phone_val, "VALUE_TYPE": "WORK"}] if phone_val else [],
        "EMAIL": [{"VALUE": email_val, "VALUE_TYPE": "WORK"}] if email_val else [],
    }})
    contact_id = contact_res.get("result")

    # 2. Company
    nip     = company.get("nip", "")
    regon   = company.get("regon", "")
    address = company.get("address", "")
    co_lines = [f"NIP: {nip}"]
    if regon:   co_lines.append(f"REGON: {regon}")
    if address: co_lines.append(f"Adres: {address}")

    company_res = await _bx("crm.company.add", {"fields": {
        "TITLE":    company.get("name", "Firma"),
        "COMMENTS": "\n".join(co_lines),
    }})
    company_id = company_res.get("result")

    # 3. Deal (stage index 0 = Nowy)
    stage_id    = await _stage(0)
    session_url = f"{APP_BASE_URL}/?session={session_id}" if APP_BASE_URL else ""
    deal_fields: dict = {
        "TITLE":       f"Wdrozenie Bitrix24 - {company.get('name', 'Nowy klient')}",
        "CATEGORY_ID": int(BITRIX24_PIPELINE_ID or 0),
        "STAGE_ID":    stage_id,
        "SOURCE_ID":   "WEB",
        "COMMENTS":    f"Lead z AD SelfIntegrator\n{session_url}",
    }
    if contact_id: deal_fields["CONTACT_ID"] = contact_id
    if company_id: deal_fields["COMPANY_ID"] = company_id

    deal_res = await _bx("crm.deal.add", {"fields": deal_fields})
    deal_id  = deal_res.get("result")

    if deal_id:
        logger.info("Bitrix24: created deal %s (stage %s) for session %s",
                    deal_id, stage_id, session_id)
        return str(deal_id)

    logger.warning("Bitrix24: deal creation returned no ID - %s", deal_res)
    return None


async def add_interview_comment(deal_id: str, interview: dict) -> None:
    """
    Post interview Q&A as a timeline comment and advance deal to stage index 1
    (Odpowiedzi - answers received).
    """
    if not BITRIX24_WEBHOOK_URL or not deal_id:
        return

    labels = {
        "team_size":          "Zespol sprzedazy",
        "lead_sources":       "Zrodla leadow",
        "current_tools":      "Obecne narzedzia",
        "sales_process":      "Proces sprzedazy",
        "telephony_needed":   "Telefonia VoIP",
        "integrations":       "Integracje",
        "automations_needed": "Automatyzacje",
        "budget":             "Budzet",
        "timeline":           "Termin uruchomienia",
    }
    lines = ["Wywiad z klientem (AD SelfIntegrator)", ""]
    for key, label in labels.items():
        val = interview.get(key)
        if val is not None and str(val).strip():
            lines.append(f"- {label}: {val}")

    await _bx("crm.timeline.comment.add", {"fields": {
        "ENTITY_TYPE_ID": DEAL_ENTITY_TYPE,
        "ENTITY_ID":      int(deal_id),
        "COMMENT":        "\n".join(lines),
    }})

    # Advance to Odpowiedzi (stage index 1)
    await _move_deal(deal_id, 1)


async def add_proposal_comment(
    deal_id: str,
    session_id: str,
    total_net: int,
    total_gross: int,
    html_bytes: bytes | None = None,
) -> None:
    """
    Post proposal summary + download link, attach HTML file to FIELD_OFERTA,
    and advance deal to stage index 2 (Oferta).
    """
    if not BITRIX24_WEBHOOK_URL or not deal_id:
        return

    proposal_url = f"{APP_BASE_URL}/api/session/{session_id}/proposal.pdf" if APP_BASE_URL else ""
    lines = [
        "Oferta handlowa przygotowana",
        "",
        f"Wartosc netto:  {total_net} PLN",
        f"Wartosc brutto: {total_gross} PLN",
    ]
    if proposal_url:
        lines += ["", f"Pobierz oferte: {proposal_url}"]

    await _bx("crm.timeline.comment.add", {"fields": {
        "ENTITY_TYPE_ID": DEAL_ENTITY_TYPE,
        "ENTITY_ID":      int(deal_id),
        "COMMENT":        "\n".join(lines),
    }})

    # Attach HTML file to the "Oferta" file field
    if html_bytes:
        await _attach_file(deal_id, FIELD_OFERTA, f"Oferta_{session_id[:8]}.html", html_bytes)

    # Advance to Oferta (stage index 2)
    await _move_deal(deal_id, 2)


async def add_contract_comment(
    deal_id: str,
    session_id: str,
    html_bytes: bytes | None = None,
) -> None:
    """
    Post contract download link, attach HTML file to FIELD_UMOWA,
    and advance deal to stage index 3 (Umowa).
    """
    if not BITRIX24_WEBHOOK_URL or not deal_id:
        return

    contract_url = f"{APP_BASE_URL}/api/session/{session_id}/contract.pdf" if APP_BASE_URL else ""
    lines = ["Umowa przygotowana i gotowa do pobrania."]
    if contract_url:
        lines += ["", f"Pobierz umowe: {contract_url}"]

    await _bx("crm.timeline.comment.add", {"fields": {
        "ENTITY_TYPE_ID": DEAL_ENTITY_TYPE,
        "ENTITY_ID":      int(deal_id),
        "COMMENT":        "\n".join(lines),
    }})

    # Attach HTML file to the "Umowa" file field
    if html_bytes:
        await _attach_file(deal_id, FIELD_UMOWA, f"Umowa_{session_id[:8]}.html", html_bytes)

    # Advance to Umowa (stage index 3)
    await _move_deal(deal_id, 3)
