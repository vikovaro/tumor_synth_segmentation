import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path


class LoggingService:
    """Сервис логирования"""
    
    def __init__(self, log_file: str = "dicom_client.log"):
        self.log_file = log_file
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
    
    def log_operation(self, operation: str, status: str, details: Dict[str, Any]):
        """Записать операцию в лог"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'status': status,
            'details': details
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except IOError as e:
            print(f"Ошибка при записи в лог: {e}")


class StatisticsService:
    """Сервис статистики"""
    
    def __init__(self, file_repo):
        self.file_repo = file_repo
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Получить статистику локального хранилища"""
        return {
            'total_patients': len(self.file_repo.list_patients()),
            'storage_size_bytes': self.file_repo.get_storage_size(),
            'storage_size_mb': self.file_repo.get_storage_size() / (1024 * 1024)
        }