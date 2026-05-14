from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from datetime import date
import logging

from services.translations import T, scope_item as _scope_item

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

PRINT_WRAPPER = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  @media screen {{
    body {{ margin: 0; background: #f0f0f0; }}
    .print-bar {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 999;
      background: #C2FF85; padding: 10px 20px;
      display: flex; align-items: center; justify-content: space-between;
      font-family: Arial, sans-serif; font-size: 14px; font-weight: 600;
      color: #111; box-shadow: 0 2px 8px rgba(0,0,0,.15);
    }}
    .print-bar button {{
      background: #111; color: #C2FF85; border: none;
      padding: 8px 24px; border-radius: 200px; font-size: 14px;
      font-weight: 700; cursor: pointer; font-family: Arial, sans-serif;
    }}
    .doc-wrap {{ margin-top: 52px; padding: 20px; }}
  }}
  @media print {{
    .print-bar {{ display: none !important; }}
    .doc-wrap {{ margin: 0; padding: 0; }}
  }}
</style>
</head><body>
<div class="print-bar">
  <span>Alpha Digital · {doctype}</span>
  <button onclick="window.print()">Drukuj / Zapisz PDF</button>
</div>
<div class="doc-wrap">{content}</div>
</body></html>"""


def _extract_body(html: str) -> str:
    """Extract content between <body> tags."""
    import re
    m = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL)
    return m.group(1) if m else html


def _extract_styles(html: str) -> str:
    """Extract <style> blocks."""
    import re
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
    return "<style>" + "\n".join(styles) + "</style>" if styles else ""


def _html_to_pdf(html: str) -> bytes:
    """
    Return the rendered HTML as UTF-8 bytes.
    Files are attached to Bitrix24 with a .html extension so managers can
    open them in a browser and print to PDF — no native system libs required.
    """
    return html.encode("utf-8")


def _proposal_render_ctx(session_data: dict) -> dict:
    """
    Build Jinja2 render context for the proposal template:
    - adds ``t`` (translation dict for the chosen language)
    - translates scope item names if language != "pl"
    """
    language = session_data.get("language") or "pl"
    if language not in T:
        language = "pl"
    t = T[language]

    # Translate scope item names when not in Polish
    scope = session_data.get("scope", [])
    if language != "pl" and scope:
        scope = [
            {**item, "item": _scope_item(item.get("item", ""), language)}
            for item in scope
        ]

    ctx = {**session_data, "t": t, "language": language}
    if scope:
        ctx["scope"] = scope
    return ctx


def generate_proposal_pdf(session_data: dict) -> bytes:
    """Return wrapped HTML (for browser display with print button)."""
    template = env.get_template("proposal.html")
    ctx = _proposal_render_ctx(session_data)
    html = template.render(
        **ctx,
        today=date.today().strftime("%d.%m.%Y"),
        proposal_number=f"OF/{date.today().strftime('%Y%m%d')}/{session_data.get('session_id', '001')[:6].upper()}",
    )
    wrapped = PRINT_WRAPPER.format(
        doctype=ctx["t"].get("doc_title", "Oferta handlowa"),
        content=_extract_styles(html) + _extract_body(html),
    )
    return wrapped.encode("utf-8")


def generate_contract_pdf(session_data: dict) -> bytes:
    """Return wrapped HTML for contract (always Polish)."""
    template = env.get_template("contract.html")
    html = template.render(
        **session_data,
        today=date.today().strftime("%d.%m.%Y"),
        contract_number=f"UMW/{date.today().strftime('%Y%m%d')}/{session_data.get('session_id', '001')[:6].upper()}",
    )
    wrapped = PRINT_WRAPPER.format(
        doctype="Umowa o swiadczenie uslug",
        content=_extract_styles(html) + _extract_body(html),
    )
    return wrapped.encode("utf-8")


# ── HTML versions for Bitrix24 file attachments ───────────────────────────────
# Attached as .html — managers open in browser and print to PDF if needed.

def generate_proposal_pdf_file(session_data: dict) -> bytes:
    """Return rendered HTML bytes for Bitrix24 attachment (proposal)."""
    template = env.get_template("proposal.html")
    ctx = _proposal_render_ctx(session_data)
    html = template.render(
        **ctx,
        today=date.today().strftime("%d.%m.%Y"),
        proposal_number=f"OF/{date.today().strftime('%Y%m%d')}/{session_data.get('session_id', '001')[:6].upper()}",
    )
    return _html_to_pdf(html)


def generate_contract_pdf_file(session_data: dict) -> bytes:
    """Return rendered HTML bytes for Bitrix24 attachment (contract, always Polish)."""
    template = env.get_template("contract.html")
    html = template.render(
        **session_data,
        today=date.today().strftime("%d.%m.%Y"),
        contract_number=f"UMW/{date.today().strftime('%Y%m%d')}/{session_data.get('session_id', '001')[:6].upper()}",
    )
    return _html_to_pdf(html)
