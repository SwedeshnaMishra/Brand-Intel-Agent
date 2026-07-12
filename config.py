import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "llama3.2")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
SCRAPER_PROXY_URL = os.getenv("SCRAPER_PROXY_URL", "") or None
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "5"))
EXCEL_OUTPUT_PATH = os.getenv("EXCEL_OUTPUT_PATH", "output.xlsx")
MARKDOWN_OUTPUT_DIR = os.getenv("MARKDOWN_OUTPUT_DIR", ".")

AMAZON_BASE_URL = "https://www.amazon.in"