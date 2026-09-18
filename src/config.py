# Configuration for Executive Productivity Agent
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Reference Evaluation Date (Anchor for overdue & due today calculations)
REFERENCE_DATE = "2026-09-18"

# Executive Profile
EXECUTIVE_NAME = "Arjun Malhotra"
EXECUTIVE_TITLE = "VP Sales"
EXECUTIVE_EMAIL = "arjun.malhotra@company.com"

# Ensure directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
(RAW_DATA_DIR / "transcripts").mkdir(exist_ok=True)
(RAW_DATA_DIR / "calendars").mkdir(exist_ok=True)
(RAW_DATA_DIR / "emails").mkdir(exist_ok=True)
(RAW_DATA_DIR / "voice_notes").mkdir(exist_ok=True)
(RAW_DATA_DIR / "directory").mkdir(exist_ok=True)
