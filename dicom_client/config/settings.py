import os
from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Настройки Orthanc сервера
    ORTHANC_URL: str = "http://localhost:8042" # todo use cfg instead
    ORTHANC_USERNAME: str = "orthanc"
    ORTHANC_PASSWORD: str = "orthanc"
    
    # Настройки локального хранилища
    LOCAL_STORAGE_PATH: str = "./dicom_storage"
    
    # Таймауты для HTTP запросов
    REQUEST_TIMEOUT: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()