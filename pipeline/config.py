"""Central configuration for the Cottonil data pipeline."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

# Source data (kept out of git; documented in README)
TABLES_DIR = BASE_DIR / "COTTONIL" / "COTTONIL_Data" / "02_TABLES"
CATALOG_DIR = BASE_DIR / "COTTONIL" / "COTTONIL_Data" / "01_CATALOG"

# Built artifacts
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cottonil.duckdb"

# Schemas
RAW_SCHEMA = "raw"
VIEW_SCHEMA = "views"

# Pipeline-owned assets
VIEWS_DIR = Path(__file__).resolve().parent / "views"
CATALOG_DOC = Path(__file__).resolve().parent / "VIEW_CATALOG.md"

# Dataset facts (Constitution IV - documented constants)
DATA_END_DATE = "2026-10-18"  # last transaction date present in the dataset
TAX_RATE = 14.0               # nominal VAT
ENCODING = "utf-8-sig"        # CSVs are UTF-8 with Arabic names
