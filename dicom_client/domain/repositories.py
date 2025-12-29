from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities import DicomInstance, DicomPatient, DicomStudy, DicomSeries


class IDicomRepository(ABC):
    """Интерфейс репозитория для работы с DICOM данными"""
    
    @abstractmethod
    def get_instance(self, instance_id: str) -> Optional[DicomInstance]:
        """Получить DICOM инстанс по ID"""
        pass
    
    @abstractmethod
    def list_instances(self, limit: int = 100) -> List[DicomInstance]:
        """Получить список DICOM инстансов"""
        pass
    
    @abstractmethod
    def download_instance(self, instance_id: str, save_path: str) -> bool:
        """Скачать DICOM файл"""
        pass
    
    @abstractmethod
    def upload_instance(self, file_path: str) -> Optional[DicomInstance]:
        """Загрузить DICOM файл"""
        pass
    
    @abstractmethod
    def delete_instance(self, instance_id: str) -> bool:
        """Удалить DICOM инстанс"""
        pass


class IFileRepository(ABC):
    """Интерфейс репозитория для работы с файловой системой"""
    
    @abstractmethod
    def save_dicom_file(self, content: bytes, patient_id: str, 
                       study_id: str, series_id: str, 
                       instance_id: str) -> str:
        """Сохранить DICOM файл в структурированном виде"""
        pass
    
    @abstractmethod
    def read_dicom_file(self, file_path: str) -> bytes:
        """Прочитать DICOM файл"""
        pass
    
    @abstractmethod
    def get_file_path(self, patient_id: str, study_id: str, 
                     series_id: str, instance_id: str) -> str:
        """Получить путь к файлу"""
        pass