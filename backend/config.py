from dotenv import load_dotenv
from pathlib import Path
import os

# Load .env from project root (one level above backend/)
load_dotenv(Path(__file__).parent.parent / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"

# Your company details (used in proposals and contracts)
YOUR_COMPANY = {
    "name": "Alpha Digital Sp. z o.o.",
    "name_full": "ALPHA DIGITAL Spółka z ograniczoną odpowiedzialnością",
    "nip": "PL9512600558",
    "nip_short": "9512600558",
    "regon": "529152973",
    "krs": "0001114720",
    "address": "ul. Zygmunta Vogla 28/02.91, 02-963 Warszawa",
    "email": "info@alphadigital.pl",
    "phone": "+48 579 545 535",
    "website": "www.alphadigital.pl",
    "ceo": "Oleg Goncharenko",
    "ceo_title": "Prezes Zarządu",
    # Bank — PKO Bank Polski S.A.
    "bank_name": "PKO Bank Polski S.A., Oddział 24 w Warszawie",
    "bank_address": "ul. Grójecka 17, 02-021 Warszawa",
    "bic_swift": "BPKOPLPW",
    "bank_account_pln": "48 1020 1055 0000 9802 0645 2702",
    "bank_account_usd": "71 1020 1055 0000 9102 0645 2728",
    "bank_account_eur": "53 1020 1055 0000 9602 0645 2710",
    # Default account alias used in templates
    "bank_account": "PL48 1020 1055 0000 9802 0645 2702",
}
