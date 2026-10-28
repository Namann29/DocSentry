from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    run_mode: Literal["LOCAL", "DEMO", "AWS"] = "LOCAL"
    database_url: str = "sqlite:///./docsentry.db"
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_expire_minutes: int = 480
    storage_dir: Path = Path("./storage")
    corpus_dir: Path = Path("./corpus/out")
    max_upload_mb: int = 25
    max_pages: int = 300
    admin_email: str = "admin@docsentry.local"
    admin_password: str = "ChangeMe123!"
    aadhaar_hmac_key: str = "dev-only-hmac-key-change-me"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    lockout_threshold: int = 5
    lockout_minutes: int = 15
    auto_create_tables: bool = True
    # OCR
    ocr_engine: Literal["auto", "ensemble", "easyocr", "tesseract", "none"] = "auto"
    tesseract_cmd: str | None = None
    ocr_langs: str = "eng"
    easyocr_langs: str = "en"


settings = Settings()