"""Settings read from environment variables, with safe relative defaults."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'certificates.db'}")
CERT_DIR = Path(os.getenv("CERT_DIR", BASE_DIR / "certificates"))
MAX_RECIPIENTS = int(os.getenv("MAX_RECIPIENTS", "500"))
