"""Application configuration module.

Centralizes all configuration values with sensible defaults.
Environment variables can override any setting via a .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# --- Server ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# --- CORS ---
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

# --- Restaurant ---
RESTAURANT_NAME = os.getenv("RESTAURANT_NAME", "La Bella Tavola")
OPENING_HOUR = int(os.getenv("OPENING_HOUR", "11"))  # 24h format
CLOSING_HOUR = int(os.getenv("CLOSING_HOUR", "22"))
MAX_PARTY_SIZE = int(os.getenv("MAX_PARTY_SIZE", "12"))
TABLES_PER_SLOT = int(os.getenv("TABLES_PER_SLOT", "5"))

# --- Conversation ---
MAX_TURNS = int(os.getenv("MAX_TURNS", "30"))
IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", "120"))
