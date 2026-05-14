"""
Bitrix24 configuration ZIP generator + HTML generators for TZ and README PDFs.

Exports:
  generate_config_zip(interview, company) -> bytes       — ZIP ready for BX24 import
  generate_tz_html(interview, company, user_info, proposal_data) -> str
  generate_readme_html(interview, company) -> str
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)

# ---------------------------------------------------------------------------
# Stage / source / field parsers
# ---------------------------------------------------------------------------

_DEFAULT_STAGES = [
    "Nowy lead",
    "Kwalifikacja",
    "Oferta wysłana",
    "Negocjacje",
    "Zamknięcie",
]

_DEFAULT_SOURCES = [
    ("CALL",           "Połączenie telefoniczne", "20", True),
    ("WEB",            "Strona internetowa",      "30", True),
    ("EMAIL",          "E-mail",                  "40", True),
    ("RECOMMENDATION", "Polecenie",               "50", True),
]

_SOURCE_KEYWORDS: list[tuple[list[str], str, str]] = [
    (["strona", "www", "web", "formularz", "witryn"],    "WEB",            "Strona internetowa / formularz"),
    (["telefon", "call", "dzwon", "połączen"],            "CALL",           "Połączenie telefoniczne"),
    (["polecen", "rekomendac", "referral"],               "RECOMMENDATION", "Polecenie / rekomendacja"),
    (["facebook", "fb"],                                  "FACEBOOK",       "Facebook"),
    (["instagram", "ig"],                                 "INSTAGRAM",      "Instagram"),
    (["linkedin"],                                        "LINKEDIN",       "LinkedIn"),
    (["targi", "trade", "konferencj", "event"],           "TRADE_SHOW",     "Targi / konferencja"),
    (["cold", "mailing", "kampani"],                      "CALLBACK",       "Cold mailing / kampania"),
    (["whatsapp"],                                        "WHATSAPP",       "WhatsApp"),
    (["telegram"],                                        "TELEGRAM",       "Telegram"),
    (["e-mail", "email", "poczta", "mail"],               "EMAIL",          "E-mail"),
]

_FIELD_KEYWORDS: list[tuple[list[str], str, str, str]] = [
    # (keywords, field_suffix, user_type, label)
    (["branż", "branz", "industry", "sektor"],              "INDUSTRY",        "string",      "Branża"),
    (["budżet", "budzet", "budget"],                         "BUDGET",          "string",      "Budżet"),
    (["termin", "deadline", "data zakończ"],                 "DEADLINE",        "date",        "Termin realizacji"),
    (["liczba pracow", "zatrudn", "wielko", "employees"],    "EMPLOYEES",       "string",      "Liczba pracowników"),
    (["nip", "vat"],                                         "NIP",             "string",      "NIP"),
    (["regon"],                                              "REGON",           "string",      "REGON"),
    (["priorytet", "priority"],                              "PRIORITY",        "enumeration", "Priorytet"),
    (["region", "województw", "miasto", "city"],             "REGION",          "string",      "Region / miasto"),
    (["produkt", "usługa", "ofert"],                         "PRODUCT",         "string",      "Produkt / usługa"),
    (["opis", "uwagi", "notatk", "komentarz"],               "NOTES",           "string",      "Uwagi / notatki"),
    (["etap", "faza", "stage"],                              "STAGE_CUSTOM",    "string",      "Etap projektu"),
    (["wartość", "wartosc", "kwota", "value"],               "VALUE",           "string",      "Wartość kontraktu"),
    (["zgoda", "rodo", "consent"],                           "CONSENT",         "boolean",     "Zgoda RODO"),
    (["kanał", "kanal", "source", "żródło", "zrodlo"],       None,              None,          None),  # skip — use SOURCE
]

_SKIP_FIELD_WORDS = {"źródło", "zrodlo", "source", "kanał", "kanal", "tak", "nie", "brak"}


def _parse_stages(sales_process: str) -> list[str]:
    """Extract ordered stage names from free-text sales_process field."""
    text = (sales_process or "").strip()
    if not text:
        return _DEFAULT_STAGES[:]

    # Try splitting on arrows
    for sep in ["→", "->", "=>", "»"]:
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts

    # Try numbered list: "1. Foo 2. Bar" or "1) Foo 2) Bar"
    numbered = re.findall(r"\d+[\.\)]\s*([^\d\.\)]+?)(?=\d+[\.\)]|$)", text)
    if len(numbered) >= 2:
        return [s.strip().rstrip(",;") for s in numbered if s.strip()]

    # Try comma / semicolon split
    for sep in [";", ","]:
        parts = [p.strip() for p in text.split(sep) if p.strip()]
        if len(parts) >= 2:
            return parts

    # Try dash-separated (but only if we have multiple dashes)
    parts = [p.strip() for p in re.split(r"\s+-\s+", text) if p.strip()]
    if len(parts) >= 2:
        return parts

    return _DEFAULT_STAGES[:]


def _parse_sources(lead_sources: str) -> list[tuple[str, str]]:
    """
    Return list of (STATUS_ID, NAME) for recognized source keywords.
    Falls back to a basic set if nothing recognized.
    """
    text = (lead_sources or "").lower()
    found: list[tuple[str, str]] = []
    seen_ids: set[str] = set()

    for keywords, status_id, name in _SOURCE_KEYWORDS:
        if any(kw in text for kw in keywords):
            if status_id not in seen_ids:
                found.append((status_id, name))
                seen_ids.add(status_id)

    if not found:
        # Return safe defaults
        return [
            ("CALL",           "Połączenie telefoniczne"),
            ("WEB",            "Strona internetowa"),
            ("EMAIL",          "E-mail"),
            ("RECOMMENDATION", "Polecenie"),
        ]
    return found


def _parse_custom_fields(client_data_fields: str, crm_sections: str) -> list[dict]:
    """
    Return list of field-definition dicts to generate UF_ custom fields.
    Each dict: {suffix, label, user_type, entity_ids}
    entity_ids: list of CRM entity strings to apply the field to.
    """
    text = (client_data_fields or "").lower()
    sections_text = (crm_sections or "").lower()

    # Which entities are relevant
    entities: list[str] = []
    if any(w in sections_text for w in ["lead", "leady"]):
        entities.append("CRM_LEAD")
    if any(w in sections_text for w in ["deal", "ofert", "szans"]):
        entities.append("CRM_DEAL")
    if any(w in sections_text for w in ["contact", "kontakt"]):
        entities.append("CRM_CONTACT")
    if any(w in sections_text for w in ["compan", "firm"]):
        entities.append("CRM_COMPANY")
    if not entities:
        entities = ["CRM_LEAD", "CRM_DEAL"]

    fields: list[dict] = []
    seen_suffixes: set[str] = set()

    for keywords, suffix, user_type, label in _FIELD_KEYWORDS:
        if suffix is None:
            continue
        if any(kw in text for kw in keywords):
            if suffix not in seen_suffixes:
                seen_suffixes.add(suffix)
                fields.append({
                    "suffix": suffix,
                    "label": label,
                    "user_type": user_type,
                    "entity_ids": entities,
                })

    return fields


# ---------------------------------------------------------------------------
# JSON structure builders
# ---------------------------------------------------------------------------

_STAGE_COLORS = [
    "#39a8ef", "#2fc6f6", "#47d5b0", "#c0de00", "#f6c523",
    "#f98531", "#ef7386", "#d36ade", "#9871db", "#6d79de",
]


def _build_deal_stage_json(stages: list[str], category_id: int = 0) -> dict:
    entity_id = f"DEAL_STAGE_{category_id}" if category_id else "DEAL_STAGE"
    pipeline_name = "Sprzedaż" if not category_id else f"Lejek {category_id}"
    cat_str = str(category_id)  # CATEGORY_ID for work stages

    items = []

    # Opening system stage
    items.append({
        "ID": "100",
        "ENTITY_ID": entity_id,
        "STATUS_ID": "NEW",
        "NAME": stages[0] if stages else "Nowy lead",
        "NAME_INIT": "W toku",
        "SORT": "10",
        "SYSTEM": "Y",
        "COLOR": "#39a8ef",
        "SEMANTICS": None,
        "CATEGORY_ID": None,
    })

    # Middle work stages — STATUS_ID must be plain integers "1", "2", … (Bitrix24 format)
    for i, stage_name in enumerate(stages[1:], start=1):
        color = _STAGE_COLORS[i % len(_STAGE_COLORS)]
        items.append({
            "ID": str(100 + i),
            "ENTITY_ID": entity_id,
            "STATUS_ID": str(i),
            "NAME": stage_name,
            "NAME_INIT": "",
            "SORT": str(10 + i * 10),
            "SYSTEM": "N",
            "COLOR": color,
            "SEMANTICS": None,
            "CATEGORY_ID": cat_str,
        })

    # Terminal stages
    items.append({
        "ID": "200",
        "ENTITY_ID": entity_id,
        "STATUS_ID": "WON",
        "NAME": "Zamknięty Wygrany",
        "NAME_INIT": "Zamknięty Wygrany",
        "SORT": "200",
        "SYSTEM": "Y",
        "COLOR": "#7BD500",
        "SEMANTICS": "S",
        "CATEGORY_ID": None,
    })
    items.append({
        "ID": "201",
        "ENTITY_ID": entity_id,
        "STATUS_ID": "LOSE",
        "NAME": "Zamknięty Stracony",
        "NAME_INIT": "Zamknięty Stracony",
        "SORT": "210",
        "SYSTEM": "Y",
        "COLOR": "#ff5752",
        "SEMANTICS": "F",
        "CATEGORY_ID": None,
    })

    return {
        "ENTITY": {
            "ID": entity_id,
            "NAME": pipeline_name,
            "SEMANTIC_INFO": {
                "START_FIELD": "NEW",
                "FINAL_SUCCESS_FIELD": "WON",
                "FINAL_UNSUCCESS_FIELD": "LOSE",
                "FINAL_SORT": 0,
            },
            "FIELD_ATTRIBUTE_SCOPE": "",
            "ENTITY_TYPE_ID": 2,
            "CATEGORY_ID": category_id,
        },
        "ITEMS": items,
    }


def _build_source_json(sources: list[tuple[str, str]]) -> dict:
    items = []
    system_ids = {"CALL", "EMAIL", "WEB", "RECOMMENDATION", "CALLBACK", "PARTNER", "OTHER"}
    sort_val = 20
    for status_id, name in sources:
        is_system = status_id in system_ids
        items.append({
            "ID": str(sort_val),
            "ENTITY_ID": "SOURCE",
            "STATUS_ID": status_id,
            "NAME": name,
            "NAME_INIT": name,
            "SORT": str(sort_val),
            "SYSTEM": "Y" if is_system else "N",
            "COLOR": "#",
            "SEMANTICS": None,
            "CATEGORY_ID": None,
        })
        sort_val += 10
    return {
        "ENTITY": {"ID": "SOURCE", "NAME": "Źródła"},
        "ITEMS": items,
    }


def _build_contact_type_json() -> dict:
    return {
        "ENTITY": {"ID": "CONTACT_TYPE", "NAME": "Typ kontaktu"},
        "ITEMS": [
            {"ID": "10", "ENTITY_ID": "CONTACT_TYPE", "STATUS_ID": "CLIENT",   "NAME": "Klient",     "NAME_INIT": "Klient",     "SORT": "10", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "20", "ENTITY_ID": "CONTACT_TYPE", "STATUS_ID": "SUPPLIER", "NAME": "Dostawca",   "NAME_INIT": "Dostawca",   "SORT": "20", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "30", "ENTITY_ID": "CONTACT_TYPE", "STATUS_ID": "PARTNER",  "NAME": "Partner",    "NAME_INIT": "Partner",    "SORT": "30", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "40", "ENTITY_ID": "CONTACT_TYPE", "STATUS_ID": "OTHER",    "NAME": "Inny",       "NAME_INIT": "Inny",       "SORT": "40", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
        ],
    }


def _build_company_type_json() -> dict:
    return {
        "ENTITY": {"ID": "COMPANY_TYPE", "NAME": "Typ firmy"},
        "ITEMS": [
            {"ID": "10", "ENTITY_ID": "COMPANY_TYPE", "STATUS_ID": "CUSTOMER",    "NAME": "Klient",     "NAME_INIT": "Klient",     "SORT": "10", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "20", "ENTITY_ID": "COMPANY_TYPE", "STATUS_ID": "SUPPLIER",    "NAME": "Dostawca",   "NAME_INIT": "Dostawca",   "SORT": "20", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "30", "ENTITY_ID": "COMPANY_TYPE", "STATUS_ID": "COMPETITOR",  "NAME": "Konkurent",  "NAME_INIT": "Konkurent",  "SORT": "30", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "40", "ENTITY_ID": "COMPANY_TYPE", "STATUS_ID": "PARTNER",     "NAME": "Partner",    "NAME_INIT": "Partner",    "SORT": "40", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "50", "ENTITY_ID": "COMPANY_TYPE", "STATUS_ID": "OTHER",       "NAME": "Inny",       "NAME_INIT": "Inny",       "SORT": "50", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
        ],
    }


def _build_deal_type_json() -> dict:
    return {
        "ENTITY": {"ID": "DEAL_TYPE", "NAME": "Typ transakcji"},
        "ITEMS": [
            {"ID": "10", "ENTITY_ID": "DEAL_TYPE", "STATUS_ID": "GOODS",    "NAME": "Sprzedaż towarów",  "NAME_INIT": "Sprzedaż towarów",  "SORT": "10", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "20", "ENTITY_ID": "DEAL_TYPE", "STATUS_ID": "SERVICE",  "NAME": "Sprzedaż usług",    "NAME_INIT": "Sprzedaż usług",    "SORT": "20", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
            {"ID": "30", "ENTITY_ID": "DEAL_TYPE", "STATUS_ID": "COMPLEX",  "NAME": "Kompleksowe",       "NAME_INIT": "Kompleksowe",       "SORT": "30", "SYSTEM": "Y", "COLOR": "#", "SEMANTICS": None, "CATEGORY_ID": None},
        ],
    }


_USER_TYPE_META: dict[str, dict] = {
    "string": {
        "USER_TYPE_ID": "string",
        "CLASS_NAME": "Bitrix\\Main\\UserField\\Types\\StringType",
        "EDIT_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\StringType", "renderEdit"],
        "VIEW_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\StringType", "renderView"],
        "USE_FIELD_COMPONENT": True,
        "DESCRIPTION": "String",
        "BASE_TYPE": "string",
    },
    "date": {
        "USER_TYPE_ID": "date",
        "CLASS_NAME": "Bitrix\\Main\\UserField\\Types\\DateType",
        "EDIT_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\DateType", "renderEdit"],
        "VIEW_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\DateType", "renderView"],
        "USE_FIELD_COMPONENT": True,
        "DESCRIPTION": "Date",
        "BASE_TYPE": "string",
    },
    "boolean": {
        "USER_TYPE_ID": "boolean",
        "CLASS_NAME": "Bitrix\\Main\\UserField\\Types\\BooleanType",
        "EDIT_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\BooleanType", "renderEdit"],
        "VIEW_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\BooleanType", "renderView"],
        "USE_FIELD_COMPONENT": True,
        "DESCRIPTION": "Yes/No",
        "BASE_TYPE": "int",
    },
    "enumeration": {
        "USER_TYPE_ID": "enumeration",
        "CLASS_NAME": "Bitrix\\Main\\UserField\\Types\\EnumType",
        "EDIT_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\EnumType", "renderEdit"],
        "VIEW_CALLBACK": ["Bitrix\\Main\\UserField\\Types\\EnumType", "renderView"],
        "USE_FIELD_COMPONENT": True,
        "DESCRIPTION": "List",
        "BASE_TYPE": "int",
    },
}


def _settings_for_type(user_type: str, label: str) -> tuple[dict, list[dict] | None]:
    """Return (SETTINGS dict, ITEMS list or None) for a given user_type."""
    if user_type == "string":
        return {"SIZE": 20, "ROWS": 1, "REGEXP": "", "MIN_LENGTH": 0, "MAX_LENGTH": 0, "DEFAULT_VALUE": ""}, None
    if user_type == "date":
        return {"DEFAULT_VALUE": ""}, None
    if user_type == "boolean":
        return {"DEFAULT_VALUE": ""}, None
    if user_type == "enumeration":
        if "priorytet" in label.lower() or "priority" in label.lower():
            option_values = ["Niski", "Średni", "Wysoki", "Krytyczny"]
        else:
            option_values = ["Opcja 1", "Opcja 2", "Opcja 3"]
        items = [
            {"ID": str(i + 1), "VALUE": v, "DEF": "N" if i > 0 else "Y", "SORT": str((i + 1) * 10)}
            for i, v in enumerate(option_values)
        ]
        return {"DISPLAY": "LIST", "LIST_HEIGHT": 1}, items
    return {"SIZE": 20, "ROWS": 1, "REGEXP": "", "MIN_LENGTH": 0, "MAX_LENGTH": 0, "DEFAULT_VALUE": ""}, None


def _build_crm_fields_json(entity_type: str, entity_name: str, field_defs: list[dict]) -> dict:
    """Build CRM_FIELDS/CRM_*.json structure for the given entity."""
    # Filter to fields applicable to this entity
    applicable = [f for f in field_defs if entity_type in f.get("entity_ids", [])]

    items: dict[str, Any] = {}
    sort_val = 100
    for fd in applicable:
        suffix = fd["suffix"]
        label = fd["label"]
        user_type = fd["user_type"]
        field_name = f"UF_CRM_{suffix}"

        settings, enum_items = _settings_for_type(user_type, label)

        user_type_meta = _USER_TYPE_META.get(user_type, _USER_TYPE_META["string"])
        field_def: dict[str, Any] = {
            "ID": str(sort_val),
            "ENTITY_ID": entity_type,
            "FIELD_NAME": field_name,
            "USER_TYPE_ID": user_type,
            "XML_ID": suffix,
            "SORT": str(sort_val),
            "MULTIPLE": "N",
            "MANDATORY": "N",
            "SHOW_FILTER": "N",
            "SHOW_IN_LIST": "Y",
            "EDIT_IN_LIST": "Y",
            "IS_SEARCHABLE": "N",
            "SETTINGS": settings,
            "EDIT_FORM_LABEL": label,
            "LIST_COLUMN_LABEL": label,
            "LIST_FILTER_LABEL": label,
            "ERROR_MESSAGE": "",
            "HELP_MESSAGE": "",
            "USER_TYPE": user_type_meta,
            "VALUE": False,
        }
        if enum_items is not None:
            field_def["ITEMS"] = enum_items

        items[field_name] = field_def
        sort_val += 10

    return {
        "TYPE": entity_type,
        "ENTITY_TYPE_NAME": entity_name,
        "ITEMS": items,
    }


def _build_bizproc_json(stages: list[str]) -> dict:
    """Build a basic automation template: notify on new lead / stage change."""
    return {
        "ID": 1,
        "MODULE_ID": "crm",
        "ENTITY": "CCrmDocumentLead",
        "DOCUMENT_TYPE": "LEAD",
        "DOCUMENT_STATUS": "NEW",
        "NAME": "Powiadomienie o nowym leadzie",
        "AUTO_EXECUTE": 8,
        "DESCRIPTION": "Automatyczne powiadomienie dla odpowiedzialnego pracownika po otrzymaniu nowego leadu.",
        "TEMPLATE_DATA": {
            "VERSION": 2,
            "TEMPLATE": [
                {
                    "Type": "SequentialWorkflowActivity",
                    "Name": "Template",
                    "Activated": "Y",
                    "Properties": {
                        "Title": "Powiadomienie o nowym leadzie",
                        "Permission": [],
                    },
                    "Children": [
                        {
                            "Type": "SendMessageActivity",
                            "Name": "NotifyResponsible",
                            "Activated": "Y",
                            "Properties": {
                                "Title": "Wyślij powiadomienie",
                                "MessageSubject": "Nowy lead: {=Document:TITLE}",
                                "MessageText": "Przydzielono Ci nowy lead: {=Document:TITLE}\nTelefon: {=Document:PHONE_WORK}\nE-mail: {=Document:EMAIL_WORK}\n\nZaloguj się do Bitrix24 i zajmij się tym leadem.",
                                "ToList": ["{=Document:ASSIGNED_BY_ID}"],
                            },
                            "Children": [],
                        }
                    ],
                }
            ],
        },
    }


def _build_rest_app_json() -> dict:
    """Placeholder for installed app entry."""
    return {
        "ID": 0,
        "APP_ID": "",
        "MODULE_ID": "rest",
        "ACTIVE": "Y",
        "STATUS": "F",
        "INSTALLED": "Y",
        "SCOPE": "crm",
    }


def _build_dynamic_types_json() -> dict:
    """Empty smart processes placeholder."""
    return {"types": []}


# ---------------------------------------------------------------------------
# Public: generate ZIP
# ---------------------------------------------------------------------------

def generate_config_zip(interview: dict, company: dict) -> bytes:
    """
    Generate a Bitrix24 configuration ZIP archive in memory.
    Returns raw ZIP bytes ready for base64 encoding and attachment.
    """
    stages = _parse_stages(interview.get("sales_process", ""))
    sources = _parse_sources(interview.get("lead_sources", ""))
    field_defs = _parse_custom_fields(
        interview.get("client_data_fields", ""),
        interview.get("crm_sections", ""),
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

        def _add(path: str, obj: Any) -> None:
            zf.writestr(path, json.dumps(obj, ensure_ascii=False, indent=2))

        # manifest.json — required by Bitrix24 import wizard ("vertical_crm" is the accepted code)
        _add("manifest.json", {
            "CODE": "vertical_crm",
            "VERSION": 1,
            "ACTIVE": "Y",
            "PLACEMENT": ["crm", "crm_lead", "crm_deal", "crm_contact", "crm_company", "crm_settings"],
            "USES": ["app", "crm", "crm_form", "bizproc_crm", "intranet_setting"],
            "TITLE": "Konfiguracja CRM — Alpha Digital",
            "DESCRIPTION": "Indywidualna konfiguracja CRM przygotowana przez Alpha Digital na podstawie wywiadu z klientem.",
            "COLOR": "#C2FF85",
            "ICON": "/bitrix/images/crm/configuration/vertical-crm-icon.svg",
            "EXPORT_TITLE_PAGE": "Eksportuj konfigurację CRM",
            "EXPORT_TITLE_BLOCK": "Konfiguracja CRM",
            "EXPORT_ACTION_DESCRIPTION": "Kliknij Eksport aby zapisać konfigurację CRM.",
            "METADATA": {"crm": {"enableRole": False}},
        })

        # CRM_SETTING
        _add("CRM_SETTING/LEAD_MODE.json", {"TYPE": "LEAD_MODE", "ENABLED": "N"})

        # CRM_FORM — empty list (required when crm_form is in USES)
        _add("CRM_FORM/list.json", {"list": []})

        # INTRANET_SETTINGS — minimal theme (required when intranet_setting is in USES)
        _add("INTRANET_SETTINGS/theme.json", {
            "TYPE": "theme", "ID": "light:default", "TEXT_COLOR": "light", "CODE": "default",
        })

        # CRM_STATUS
        _add("CRM_STATUS/DEAL_STAGE.json", _build_deal_stage_json(stages, category_id=0))
        _add("CRM_STATUS/SOURCE.json",      _build_source_json(sources))
        _add("CRM_STATUS/CONTACT_TYPE.json", _build_contact_type_json())
        _add("CRM_STATUS/COMPANY_TYPE.json", _build_company_type_json())
        _add("CRM_STATUS/DEAL_TYPE.json",    _build_deal_type_json())

        # CRM_FIELDS
        entity_map = [
            ("CRM_LEAD",    "LEAD"),
            ("CRM_DEAL",    "DEAL"),
            ("CRM_CONTACT", "CONTACT"),
            ("CRM_COMPANY", "COMPANY"),
        ]
        for entity_type, entity_name in entity_map:
            _add(f"CRM_FIELDS/{entity_type}.json",
                 _build_crm_fields_json(entity_type, entity_name, field_defs))

        # BIZPROC_MAIN
        _add("BIZPROC_MAIN/0.json", _build_bizproc_json(stages))

        # REST_APPLICATION
        _add("REST_APPLICATION/0.json", _build_rest_app_json())

        # CRM_DYNAMIC_TYPES
        _add("CRM_DYNAMIC_TYPES/types.json", _build_dynamic_types_json())

    return buf.getvalue()


# ---------------------------------------------------------------------------
# HTML generators for TZ and README
# ---------------------------------------------------------------------------

def _what_cannot_be_automated(interview: dict) -> list[dict]:
    """
    Return list of {title, reason} items that cannot be done via config ZIP,
    filtered to what this client actually needs.
    """
    items = []
    oc = (interview.get("open_channels") or "").lower()
    if oc and oc not in ("nie", "brak", "no", "false"):
        items.append({
            "title": "Otwarte kanały / komunikatory (WhatsApp, Telegram, Viber, Facebook Messenger, Instagram)",
            "reason": "Wymagają autoryzacji OAuth w UI Bitrix24 i podania danych konta każdego kanału z osobna.",
        })
    if interview.get("telephony_needed"):
        items.append({
            "title": "Integracja z telefonią VoIP",
            "reason": "Wymaga wpisania danych konta operatora (Zadarma, Sip2Sip, etc.) oraz konfiguracji scenariuszy IVR ręcznie w ustawieniach portalu.",
        })
    ws = (interview.get("website_integration") or "").lower()
    if ws and ws not in ("nie", "brak", "no", "false"):
        items.append({
            "title": "Widget Bitrix24 i formularze CRM na stronie www",
            "reason": "Kod widżetu musi być osadzony na stronie internetowej przez webmastera. Formularze CRM tworzy się ręcznie w kreatorze.",
        })
    if interview.get("email_integration"):
        items.append({
            "title": "Integracja skrzynki e-mail (SMTP/IMAP)",
            "reason": "Wymaga podania danych serwera pocztowego i hasła — konfiguracja per użytkownik.",
        })
    other = (interview.get("other_integrations") or "").lower()
    if other and other not in ("nie", "brak", "no", "false"):
        items.append({
            "title": "Integracje z systemami zewnętrznymi (ERP, księgowość, API)",
            "reason": "Wymagają kluczy API / danych logowania do systemów zewnętrznych oraz programistycznej konfiguracji webhooków.",
        })
    # Always add these two
    items.append({
        "title": "Tworzenie kont użytkowników i przydzielanie licencji",
        "reason": "Konta zakładane są per pracownik przez administratora portalu w Ustawieniach → Użytkownicy.",
    })
    items.append({
        "title": "Import danych z pliku (baza klientów)",
        "reason": "Import wymaga przygotowanego pliku CSV/XLS z mapowaniem kolumn — wykonywany ręcznie przez CRM → Import.",
    })
    items.append({
        "title": "Zaawansowane automatyzacje z warunkami złożonymi",
        "reason": "Złożone reguły biznesowe konfiguruje się w wizualnym edytorze automatyzacji (robotów i triggerów).",
    })
    items.append({
        "title": "Raporty, pulpity i dashboardy BI",
        "reason": "Tworzone ręcznie w sekcji CRM Analytics / BI Builder z użyciem kreatorów wizualnych.",
    })
    return items


def _what_is_in_config(interview: dict) -> list[str]:
    """Return bullet-point list of what IS included in the config ZIP."""
    stages = _parse_stages(interview.get("sales_process", ""))
    sources = _parse_sources(interview.get("lead_sources", ""))
    field_defs = _parse_custom_fields(
        interview.get("client_data_fields", ""),
        interview.get("crm_sections", ""),
    )

    items = []
    items.append(f"Etapy lejka sprzedażowego ({len(stages)} etapów): " + ", ".join(stages))
    if sources:
        items.append(f"Źródła leadów ({len(sources)}): " + ", ".join(n for _, n in sources))
    if field_defs:
        labels = [f["label"] for f in field_defs]
        items.append(f"Niestandardowe pola CRM ({len(field_defs)}): " + ", ".join(labels))
    items.append("Typy kontaktów: Klient, Dostawca, Partner, Inny")
    items.append("Typy firm: Klient, Dostawca, Konkurent, Partner, Inny")
    items.append("Typy transakcji: Sprzedaż towarów, Sprzedaż usług, Kompleksowe")
    items.append("Szablon automatyzacji: powiadomienie e-mail o nowym leadzie")
    return items


def generate_tz_html(
    interview: dict,
    company: dict,
    user_info: dict,
    proposal_data: dict,
) -> str:
    """Render the TZ (Zadanie Techniczne) HTML from the Jinja2 template."""
    stages = _parse_stages(interview.get("sales_process", ""))
    field_defs = _parse_custom_fields(
        interview.get("client_data_fields", ""),
        interview.get("crm_sections", ""),
    )
    sources = _parse_sources(interview.get("lead_sources", ""))
    cannot_list = _what_cannot_be_automated(interview)

    template = _env.get_template("technical_spec.html")
    return template.render(
        interview=interview,
        company=company,
        user_info=user_info,
        proposal_data=proposal_data,
        stages=stages,
        field_defs=field_defs,
        sources=sources,
        cannot_list=cannot_list,
        today=date.today().strftime("%d.%m.%Y"),
        doc_number=f"TZ/{date.today().strftime('%Y%m%d')}/{(interview.get('portal_email') or 'CLI')[:6].upper()}",
    )


def generate_readme_html(interview: dict, company: dict) -> str:
    """Render the README MVP HTML from the Jinja2 template."""
    in_config = _what_is_in_config(interview)
    cannot_list = _what_cannot_be_automated(interview)

    template = _env.get_template("readme_mvp.html")
    return template.render(
        interview=interview,
        company=company,
        in_config=in_config,
        cannot_list=cannot_list,
        today=date.today().strftime("%d.%m.%Y"),
    )
