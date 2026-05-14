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

    # 1. Contact — all fields mapped to proper CRM fields
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

    # 2. Company — proper CRM fields + NIP/REGON in COMMENTS
    nip     = company.get("nip", "")
    regon   = company.get("regon", "")
    address = company.get("address", "")

    co_comments_lines = []
    if nip:   co_comments_lines.append(f"NIP: {nip}")
    if regon: co_comments_lines.append(f"REGON: {regon}")

    company_fields: dict = {
        "TITLE":       company.get("name", "Firma"),
        "COMPANY_TYPE": "CUSTOMER",
    }
    if address:
        company_fields["ADDRESS"] = address
    if phone_val:
        # If user provided their work phone, link it to company too
        company_fields["PHONE"] = [{"VALUE": phone_val, "VALUE_TYPE": "WORK"}]
    if email_val:
        company_fields["EMAIL"] = [{"VALUE": email_val, "VALUE_TYPE": "WORK"}]
    if co_comments_lines:
        company_fields["COMMENTS"] = "\n".join(co_comments_lines)

    company_res = await _bx("crm.company.add", {"fields": company_fields})
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
        # Blok 1
        "team_size":               "Liczba uzytkownikow Bitrix24",
        "bitrix24_experience":     "Doswiadczenie z Bitrix24",
        "implementation_goals":    "Cele wdrozenia",
        "key_modules":             "Kluczowe moduly",
        # Blok 2
        "current_tools":           "Aktualne systemy i narzedzia",
        "data_import":             "Import bazy klientow",
        # Blok 3
        "sales_team_structure":    "Struktura dzialu sprzedazy",
        "lead_sources":            "Kanaly pozyskiwania leadow",
        "sales_process":           "Etapy lejka sprzedazowego",
        "crm_sections":            "Sekcje CRM",
        "client_data_fields":      "Pola danych klienta",
        "lead_distribution":       "Dystrybucja leadow",
        "access_rights":           "Prawa dostepu",
        "reports_needed":          "Raporty i analityki",
        # Blok 4
        "automations_needed":      "Automatyzacje i procesy",
        "has_documented_processes":"Gotowe opisy procesow",
        "external_users":          "Zewnetrzni uzytkownicy",
        # Blok 5
        "telephony_needed":        "Telefonia VoIP",
        "telephony_details":       "Szczegoly telefonii",
        "open_channels":           "Otwarte linie (komunikatory)",
        "email_integration":       "Integracja poczty e-mail",
        "website_integration":     "Integracja strony WWW",
        "other_integrations":      "Inne integracje",
        # Blok 6
        "timeline":                "Termin wdrozenia",
        "budget":                  "Budzet",
        "portal_email":            "Email portalu Bitrix24",
        "additional_comments":     "Dodatkowe komentarze",
    }
    lines = ["Wywiad z klientem (AD SelfIntegrator)", ""]
    for key, label in labels.items():
        val = interview.get(key)
        if val is not None and str(val).strip() and str(val).strip().lower() not in ("false", "none"):
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
    pdf_bytes: bytes | None = None,
) -> None:
    """
    Post proposal summary + download link, attach PDF file to FIELD_OFERTA,
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

    # Attach PDF file to the "Oferta" file field
    if pdf_bytes:
        await _attach_file(deal_id, FIELD_OFERTA, f"Oferta_{session_id[:8]}.pdf", pdf_bytes)

    # Advance to Oferta (stage index 2)
    await _move_deal(deal_id, 2)


# ---------------------------------------------------------------------------
# MVP document fields — auto-created on first use
# ---------------------------------------------------------------------------

_mvp_fields_cache: dict = {}

FIELD_TZ_LABEL     = "Zadanie techniczne"
FIELD_MVP_LABEL    = "MVP Portalu"
FIELD_README_LABEL = "Readme do MVP Portalu"

_MVP_FIELD_DEFS = [
    (FIELD_TZ_LABEL,     "tz",     "ZADANIE_TECHNICZNE"),
    (FIELD_MVP_LABEL,    "mvp",    "MVP_PORTALU"),
    (FIELD_README_LABEL, "readme", "README_MVP_PORTALU"),
]


async def _ensure_mvp_fields() -> dict:
    """
    Find or create 3 file-type custom fields on CRM_DEAL for TZ, MVP ZIP, README.
    Returns dict: {"tz": "UF_CRM_...", "mvp": "UF_CRM_...", "readme": "UF_CRM_..."}
    """
    global _mvp_fields_cache
    if _mvp_fields_cache:
        return _mvp_fields_cache

    result = await _bx("crm.userfield.list", {
        "order": {"SORT": "ASC"},
        "filter": {"ENTITY_ID": "CRM_DEAL"},
    })
    fields = result.get("result", [])

    # Map label text -> FIELD_NAME
    label_to_field: dict[str, str] = {}
    all_labels = {FIELD_TZ_LABEL, FIELD_MVP_LABEL, FIELD_README_LABEL}
    for f in fields:
        for attr in ("EDIT_FORM_LABEL", "LIST_COLUMN_LABEL"):
            val = f.get(attr, "")
            if isinstance(val, str) and val in all_labels:
                label_to_field[val] = f["FIELD_NAME"]
            elif isinstance(val, dict):
                for v in val.values():
                    if isinstance(v, str) and v in all_labels:
                        label_to_field[v] = f["FIELD_NAME"]

    # Create any missing fields
    created_any = False
    for label, _key, xml_id in _MVP_FIELD_DEFS:
        if label not in label_to_field:
            r = await _bx("crm.userfield.add", {"fields": {
                "ENTITY_ID":         "CRM_DEAL",
                "FIELD_NAME":        f"UF_CRM_AD_{xml_id[:20]}",
                "USER_TYPE_ID":      "file",
                "XML_ID":            xml_id,
                "MULTIPLE":          "N",
                "MANDATORY":         "N",
                "SHOW_IN_LIST":      "Y",
                "EDIT_IN_LIST":      "Y",
                "EDIT_FORM_LABEL":   {"pl": label, "en": label},
                "LIST_COLUMN_LABEL": {"pl": label, "en": label},
                "SORT":              "500",
            }})
            if r.get("result"):
                created_any = True
                logger.info("Created Bitrix24 field '%s' id=%s", label, r["result"])

    if created_any:
        # Re-fetch to get the actual FIELD_NAME values
        result2 = await _bx("crm.userfield.list", {
            "order": {"SORT": "ASC"},
            "filter": {"ENTITY_ID": "CRM_DEAL"},
        })
        for f in result2.get("result", []):
            for attr in ("EDIT_FORM_LABEL", "LIST_COLUMN_LABEL"):
                val = f.get(attr, "")
                if isinstance(val, str) and val in all_labels:
                    label_to_field[val] = f["FIELD_NAME"]
                elif isinstance(val, dict):
                    for v in val.values():
                        if isinstance(v, str) and v in all_labels:
                            label_to_field[v] = f["FIELD_NAME"]

    _mvp_fields_cache = {
        "tz":     label_to_field.get(FIELD_TZ_LABEL,     ""),
        "mvp":    label_to_field.get(FIELD_MVP_LABEL,    ""),
        "readme": label_to_field.get(FIELD_README_LABEL, ""),
    }
    logger.info("MVP field IDs resolved: %s", _mvp_fields_cache)
    return _mvp_fields_cache


async def add_mvp_documents(
    deal_id: str,
    tz_pdf_bytes: bytes,
    config_zip_bytes: bytes,
    readme_pdf_bytes: bytes,
    session_id: str,
) -> None:
    """Attach TZ PDF, config ZIP, and README PDF to deal custom fields."""
    if not BITRIX24_WEBHOOK_URL or not deal_id:
        return

    fields = await _ensure_mvp_fields()

    updates: dict = {}
    if tz_pdf_bytes and fields.get("tz"):
        b64 = base64.b64encode(tz_pdf_bytes).decode()
        updates[fields["tz"]] = {"fileData": [f"TZ_{session_id[:8]}.pdf", b64]}
    if config_zip_bytes and fields.get("mvp"):
        b64 = base64.b64encode(config_zip_bytes).decode()
        updates[fields["mvp"]] = {"fileData": [f"MVP_Config_{session_id[:8]}.zip", b64]}
    if readme_pdf_bytes and fields.get("readme"):
        b64 = base64.b64encode(readme_pdf_bytes).decode()
        updates[fields["readme"]] = {"fileData": [f"README_MVP_{session_id[:8]}.pdf", b64]}

    if updates:
        result = await _bx("crm.deal.update", {"id": int(deal_id), "fields": updates})
        logger.info("Attached MVP documents to deal %s (ok=%s)", deal_id, result.get("result"))


async def add_contract_comment(
    deal_id: str,
    session_id: str,
    pdf_bytes: bytes | None = None,
) -> None:
    """
    Post contract download link, attach PDF file to FIELD_UMOWA,
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

    # Attach PDF file to the "Umowa" file field
    if pdf_bytes:
        await _attach_file(deal_id, FIELD_UMOWA, f"Umowa_{session_id[:8]}.pdf", pdf_bytes)

    # Advance to Umowa (stage index 3)
    await _move_deal(deal_id, 3)
