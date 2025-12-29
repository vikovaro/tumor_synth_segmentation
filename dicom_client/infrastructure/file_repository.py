import os
from pathlib import Path
from typing import Optional
from domain.repositories import IFileRepository
from config.settings import settings


class FileRepository(IFileRepository):
    """Репозиторий для работы с файловой системой"""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or settings.LOCAL_STORAGE_PATH)
        self._ensure_directory_exists()
    
    def _ensure_directory_exists(self):
        """Создать базовую директорию если она не существует"""
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_dicom_file(self, content: bytes, patient_id: str, 
                       study_id: str, series_id: str, 
                       instance_id: str) -> str:
        """
        Сохранить DICOM файл в структурированной директории:
        base_path/patient_id/study_id/series_id/instance_id.dcm
        """
        # Создаем путь к файлу
        file_path = self.get_file_path(patient_id, study_id, series_id, instance_id)
        
        # Создаем необходимые директории
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Сохраняем файл
        try:
            with open(file_path, 'wb') as f:
                f.write(content)
            return file_path
        except IOError as e:
            print(f"Ошибка при сохранении файла: {e}")
            raise
    
    def read_dicom_file(self, file_path: str) -> bytes:
        """Прочитать DICOM файл"""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except IOError as e:
            print(f"Ошибка при чтении файла: {e}")
            raise
    
    def get_file_path(self, patient_id: str, study_id: str, 
                     series_id: str, instance_id: str) -> str:
        """Получить путь для сохранения DICOM файла"""
        # Очищаем ID от недопустимых символов для имен файлов
        safe_patient_id = self._sanitize_filename(patient_id)
        safe_study_id = self._sanitize_filename(study_id)
        safe_series_id = self._sanitize_filename(series_id)
        safe_instance_id = self._sanitize_filename(instance_id)
        
        # Создаем путь
        path = (
            self.base_path / 
            safe_patient_id / 
            safe_study_id / 
            safe_series_id / 
            f"{safe_instance_id}.dcm"
        )
        
        return str(path)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очистить имя файла от недопустимых символов"""
        # Заменяем недопустимые символы на подчеркивания
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename
    
    def list_patients(self) -> list:
        """Получить список пациентов в локальном хранилище"""
        patients = []
        for item in self.base_path.iterdir():
            if item.is_dir():
                patients.append(item.name)
        return patients
    
    def get_storage_size(self) -> int:
        """Получить общий размер хранилища в байтах"""
        total_size = 0
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        return total_size