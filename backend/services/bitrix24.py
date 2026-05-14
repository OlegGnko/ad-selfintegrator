"""
Bitrix24 CRM integration via inbound webhook.

Triggered at key moments in the sales flow:
  1. submit_user_info (with full contact data) → create Contact + Company + Deal
  2. submit_interview_data                     → add Q&A comment + proposal link
  3. approve_proposal                          → add contract link, advance stage
"""

import httpx
import logging
from config import BITRIX24_WEBHOOK_URL, BITRIX24_PIPELINE_ID, BITRIX24_STAGE_ID, APP_BASE_URL

logger = logging.getLogger(__name__)

DEAL_ENTITY_TYPE = 2   # Bitrix24 numeric entity type for CRM Deal


# ── Internal helper ──────────────────────────────────────────────────────────

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


async def _first_stage_id() -> str:
    """Return the STATUS_ID of the first stage in the configured pipeline."""
    if BITRIX24_STAGE_ID:
        return BITRIX24_STAGE_ID

    cat_id = int(BITRIX24_PIPELINE_ID or 0)
    if cat_id == 0:
        return "NEW"   # first stage of the default pipeline

    result = await _bx("crm.dealcategory.stage.list", {"id": cat_id})
    stages = result.get("result", [])
    if stages:
        return stages[0].get("STATUS_ID", f"C{cat_id}:NEW")
    return f"C{cat_id}:NEW"


# ── Public API ───────────────────────────────────────────────────────────────

async def create_deal_with_contact(
    user_info: dict, company: dict, session_id: str
) -> str | None:
    """
    Create a Bitrix24 Contact, Company and Deal linked together.
    Returns the deal ID as a string, or None if the integration is disabled.
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
    co_comment_lines = [f"NIP: {nip}"]
    if regon:
        co_comment_lines.append(f"REGON: {regon}")
    if address:
        co_comment_lines.append(f"Adres: {address}")

    company_res = await _bx("crm.company.add", {"fields": {
        "TITLE":    company.get("name", "Firma"),
        "COMMENTS": "\n".join(co_comment_lines),
    }})
    company_id = company_res.get("result")

    # 3. Stage
    stage_id = await _first_stage_id()

    # 4. Deal
    session_url = f"{APP_BASE_URL}/?session={session_id}" if APP_BASE_URL else ""
    deal_fields: dict = {
        "TITLE":       f"Wdrożenie Bitrix24 — {company.get('name', 'Nowy klient')}",
        "CATEGORY_ID": int(BITRIX24_PIPELINE_ID or 0),
        "STAGE_ID":    stage_id,
        "SOURCE_ID":   "WEB",
        "COMMENTS":    f"Lead z AD SelfIntegrator\n{session_url}",
    }
    if contact_id:
        deal_fields["CONTACT_ID"] = contact_id
    if company_id:
        deal_fields["COMPANY_ID"] = company_id

    deal_res = await _bx("crm.deal.add", {"fields": deal_fields})
    deal_id  = deal_res.get("result")

    if deal_id:
        logger.info("Bitrix24: created deal %s for session %s", deal_id, session_id)
        return str(deal_id)

    logger.warning("Bitrix24: deal creation returned no ID (response: %s)", deal_res)
    return None


async def add_interview_comment(deal_id: str, interview: dict) -> None:
    """Post interview Q&A as a timeline comment on the deal."""
    if not BITRIX24_WEBHOOK_URL or not deal_id:
        return

    labels = {
        "team_size":          "Zespół sprzedaży",
        "lead_sources":       "Źródła leadów",
        "current_tools":      "Obecne narzędzia",
        "sales_process":      "Proces sprzedaży",
        "telephony_needed":   "Telefonia VoIP",
        "integrations":       "Integracje",
        "automations_needed": "Automatyzacje",
        "budget":             "Budżet",
        "timeline":           "Termin uruchomienia",
    }
    lines = ["📋 Wywiad z klientem (AD SelfIntegrator)", ""]
    for key, label in labels.items():
        val = interview.get(key)
        if val is not None and str(val).strip():
            lines.append(f"• {label}: {val}")

    await _bx("crm.timeline.comment.add", {"fields": {
        "ENTITY_TYPE_ID": DEAL_ENTITY_TYPE,
        "ENTITY_ID":      int(deal_id),
        "COMMENT":        "\n".join(lines),
    }})


async def add_proposal_comment(
    deal_id: str, session_id: str, total_net: int, total_gross: int
) -> None:
    """Post proposal summary + download link as a timeline comment."""
    if not BITRIX24_WEBHOOK_URL or not deal_id:
        return

    proposal_url = (
        f"{APP_BASE_URL}/api/session/{session_id}/proposal.pdf"
        if APP_BASE_URL else ""
    )
    lines = [
        "📄 Oferta handlowa przygotowana",
        "",
        f"Wartość netto:  {total_net:,} PLN".replace(",", " "),
        f"Wartość brutto: {total_gross:,} PLN".replace(",", " "),
    ]
    if proposal_url:
        lines += ["", f"🔗 Pobierz ofertę: {proposal_url}"]

    await _bx("crm.timeline.comment.add", {"fields": {
        "ENTITY_TYPE_ID": DEAL_ENTITY_TYPE,
        "ENTITY_ID":      int(deal_id),
        "COMMENT":        "\n".join(lines),
    }})


async def add_contract_comment(deal_id: str, session_id: str) -> None:
    """Post contract download link as a timeline comment and advance deal stage."""
    if not BITRIX24_WEBHOOK_URL or not deal_id:
        return

    contract_url = (
        f"{APP_BASE_URL}/api/session/{session_id}/contract.pdf"
        if APP_BASE_URL else ""
    )
    lines = ["📝 Umowa przygotowana i gotowa do pobrania."]
    if contract_url:
        lines += ["", f"🔗 Pobierz umowę: {contract_url}"]

    await _bx("crm.timeline.comment.add", {"fields": {
        "ENTITY_TYPE_ID": DEAL_ENTITY_TYPE,
        "ENTITY_ID":      int(deal_id),
        "COMMENT":        "\n".join(lines),
    }})
