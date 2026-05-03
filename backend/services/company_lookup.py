import httpx
from datetime import date


def validate_nip(nip: str) -> bool:
    nip = nip.replace("-", "").replace(" ", "")
    if len(nip) != 10 or not nip.isdigit():
        return False
    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    checksum = sum(int(nip[i]) * weights[i] for i in range(9)) % 11
    return checksum == int(nip[9])


async def lookup_company_by_nip(nip: str) -> dict | None:
    nip_clean = nip.replace("-", "").replace(" ", "")
    today = date.today().strftime("%Y-%m-%d")

    # Primary: MF White List (Ministerstwo Finansów) — free, no auth
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://wl-api.mf.gov.pl/api/search/nip/{nip_clean}",
                params={"date": today},
            )
            if r.status_code == 200:
                data = r.json().get("result", {}).get("subject")
                if data:
                    return _parse_mf_response(data)
    except Exception:
        pass

    # Fallback: REGON GUS (public endpoint, no auth for basic data)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://wyszukiwarkaregon.stat.gov.pl/api/Search",
                params={"Nip": nip_clean},
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                items = r.json()
                if items:
                    return _parse_regon_response(items[0])
    except Exception:
        pass

    return None


def _parse_mf_response(data: dict) -> dict:
    name = data.get("name", "")
    address = data.get("workingAddress") or data.get("residenceAddress", "")
    return {
        "name": name,
        "nip": data.get("nip", ""),
        "regon": data.get("regon", ""),
        "address": address,
        "vat_status": "Czynny podatnik VAT",
        "source": "Ministerstwo Finansów",
    }


def _parse_regon_response(data: dict) -> dict:
    return {
        "name": data.get("Nazwa", ""),
        "nip": data.get("Nip", ""),
        "regon": data.get("Regon", ""),
        "address": f"{data.get('Ulica', '')} {data.get('NrNieruchomosci', '')}, "
                   f"{data.get('KodPocztowy', '')} {data.get('Miejscowosc', '')}".strip(", "),
        "vat_status": "Aktywna",
        "source": "GUS REGON",
    }
