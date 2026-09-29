"""Pre-seed Hindsight + the local history store with realistic demo incidents.

Usage (from the backend/ folder, with .env configured):
    python seed_data.py
"""
import logging

from app.main import seed_demo
from app.services.hindsight_client import get_hindsight_service

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    get_hindsight_service().ensure_bank()
    print(seed_demo())
