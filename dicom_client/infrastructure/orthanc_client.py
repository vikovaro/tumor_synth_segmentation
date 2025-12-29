import requests
import json
from typing import Dict, List, Optional, Any
from requests.auth import HTTPBasicAuth
from domain.repositories import IDicomRepository
from domain.entities import DicomInstance
from config.settings import settings


class OrthancClient(IDicomRepository):
    """Клиент для работы с Orthanc сервером"""
    
    def __init__(self):
        self.base_url = settings.ORTHANC_URL.rstrip('/')
        self.auth = HTTPBasicAuth(
            settings.ORTHANC_USERNAME, 
            settings.ORTHANC_PASSWORD
        )
        self.timeout = settings.REQUEST_TIMEOUT
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Any]:
        """Выполнить HTTP запрос к Orthanc API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Добавляем базовую аутентификацию если не указана другая
        if 'auth' not in kwargs:
            kwargs['auth'] = self.auth
        
        # Добавляем таймаут если не указан
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            
            # Возвращаем JSON для соответствующих ответов
            if response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            return response.content
            
        except requests.RequestException as e:
            print(f"Ошибка при запросе к Orthanc: {e}")
            return None
    
    def get_instance(self, instance_id: str) -> Optional[DicomInstance]:
        """Получить информацию о DICOM инстансе"""
        data = self._make_request('GET', f'/instances/{instance_id}')
        
        if not data:
            return None
        
        # Собираем информацию о родительских ресурсах
        patient_id = self._get_parent(instance_id, 'patient')
        study_id = self._get_parent(instance_id, 'study')
        series_id = self._get_parent(instance_id, 'series')
        
        return DicomInstance(
            id=instance_id,
            patient_id=patient_id or '',
            study_id=study_id or '',
            series_id=series_id or '',
            file_size=data.get('FileSize'),
            metadata=data
        )
    
    def list_instances(self, limit: int = 100) -> List[DicomInstance]:
        """Получить список всех DICOM инстансов"""
        instances_data = self._make_request('GET', f'/instances?limit={limit}')
        
        if not instances_data or not isinstance(instances_data, list):
            return []
        
        instances = []
        for instance_id in instances_data:
            instance = self.get_instance(instance_id)
            if instance:
                instances.append(instance)
        
        return instances
    
    def download_instance(self, instance_id: str, save_path: str) -> bool:
        """Скачать DICOM файл"""
        content = self._make_request('GET', f'/instances/{instance_id}/file')
        
        if not content or not isinstance(content, bytes):
            return False
        
        try:
            with open(save_path, 'wb') as f:
                f.write(content)
            return True
        except IOError as e:
            print(f"Ошибка при сохранении файла: {e}")
            return False
    
    def upload_instance(self, file_path: str) -> Optional[DicomInstance]:
        """Загрузить DICOM файл на Orthanc сервер"""
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except IOError as e:
            print(f"Ошибка при чтении файла: {e}")
            return None
        
        # Отправляем файл на сервер
        response = self._make_request(
            'POST',
            '/instances',
            data=file_content,
            headers={'Content-Type': 'application/dicom'}
        )
        
        if not response:
            return None
        
        # Получаем информацию о загруженном инстансе
        instance_id = response.get('ID')
        if not instance_id:
            return None
        
        return self.get_instance(instance_id)
    
    def delete_instance(self, instance_id: str) -> bool:
        """Удалить DICOM инстанс с сервера"""
        response = self._make_request('DELETE', f'/instances/{instance_id}')
        return response is not None
    
    def _get_parent(self, instance_id: str, parent_type: str) -> Optional[str]:
        """Получить ID родительского ресурса"""
        data = self._make_request('GET', f'/instances/{instance_id}/{parent_type}')
        
        if data and isinstance(data, dict):
            return data.get('ID')
        return None
    
    def get_statistics(self) -> Optional[Dict]:
        """Получить статистику сервера"""
        return self._make_request('GET', '/statistics')
    
    def get_system_info(self) -> Optional[Dict]:
        """Получить информацию о системе"""
        return self._make_request('GET', '/system')