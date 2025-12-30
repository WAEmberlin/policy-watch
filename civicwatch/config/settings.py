"""
Configuration settings for the CivicWatch summarization pipeline.
"""
import os
from pathlib import Path

# Base directory (parent of civicwatch/)
BASE_DIR = Path(__file__).parent.parent.parent

# Storage directories
STORAGE_DIR = BASE_DIR / "civicwatch" / "storage"
RAW_DIR = STORAGE_DIR / "raw"
NORMALIZED_DIR = STORAGE_DIR / "normalized"
CHUNKS_DIR = STORAGE_DIR / "chunks"
SUMMARIES_DIR = STORAGE_DIR / "summaries"
MAP_SUMMARIES_DIR = STORAGE_DIR / "summaries" / "map"
REDUCE_SUMMARIES_DIR = STORAGE_DIR / "summaries" / "reduce"

# Ensure directories exist
for dir_path in [RAW_DIR, NORMALIZED_DIR, CHUNKS_DIR, MAP_SUMMARIES_DIR, REDUCE_SUMMARIES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))

# Chunking configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))  # Characters (approximate tokens)
CHUNK_OVERLAP = float(os.getenv("CHUNK_OVERLAP", "0.15"))  # 15% overlap

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

