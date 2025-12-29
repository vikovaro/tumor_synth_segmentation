from typing import List, Optional
from domain.entities import DicomInstance
from domain.repositories import IDicomRepository, IFileRepository


class DownloadDicomUseCase:
    """Сценарий скачивания DICOM файлов"""
    
    def __init__(self, dicom_repo: IDicomRepository, file_repo: IFileRepository):
        self.dicom_repo = dicom_repo
        self.file_repo = file_repo
    
    def execute(self, instance_id: str) -> Optional[str]:
        """Скачать DICOM файл и сохранить в структурированном виде"""
        # Получаем информацию об инстансе
        instance = self.dicom_repo.get_instance(instance_id)
        if not instance:
            print(f"Инстанс {instance_id} не найден")
            return None
        
        # Скачиваем файл
        temp_path = f"/tmp/{instance_id}.dcm"
        if not self.dicom_repo.download_instance(instance_id, temp_path):
            print(f"Ошибка при скачивании инстанса {instance_id}")
            return None
        
        # Читаем скачанный файл
        try:
            with open(temp_path, 'rb') as f:
                content = f.read()
        except IOError as e:
            print(f"Ошибка при чтении временного файла: {e}")
            return None
        
        # Сохраняем в структурированное хранилище
        try:
            file_path = self.file_repo.save_dicom_file(
                content,
                instance.patient_id,
                instance.study_id,
                instance.series_id,
                instance.id
            )
            print(f"Файл сохранен: {file_path}")
            return file_path
        except Exception as e:
            print(f"Ошибка при сохранении файла: {e}")
            return None
        finally:
            # Удаляем временный файл
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)


class UploadDicomUseCase:
    """Сценарий загрузки DICOM файлов"""
    
    def __init__(self, dicom_repo: IDicomRepository):
        self.dicom_repo = dicom_repo
    
    def execute(self, file_path: str) -> Optional[DicomInstance]:
        """Загрузить DICOM файл на сервер"""
        return self.dicom_repo.upload_instance(file_path)


class ListInstancesUseCase:
    """Сценарий получения списка инстансов"""
    
    def __init__(self, dicom_repo: IDicomRepository):
        self.dicom_repo = dicom_repo
    
    def execute(self, limit: int = 100) -> List[DicomInstance]:
        """Получить список DICOM инстансов"""
        return self.dicom_repo.list_instances(limit)


class SyncDicomUseCase:
    """Сценарий синхронизации DICOM файлов"""
    
    def __init__(self, dicom_repo: IDicomRepository, file_repo: IFileRepository):
        self.dicom_repo = dicom_repo
        self.file_repo = file_repo
    
    def execute(self, limit: int = 100) -> List[str]:
        """Синхронизировать все инстансы с сервера"""
        instances = self.dicom_repo.list_instances(limit)
        downloaded_files = []
        
        print(f"Найдено {len(instances)} инстансов для синхронизации")
        
        for i, instance in enumerate(instances, 1):
            print(f"Скачивание {i}/{len(instances)}: {instance.id}")
            
            use_case = DownloadDicomUseCase(self.dicom_repo, self.file_repo)
            file_path = use_case.execute(instance.id)
            
            if file_path:
                downloaded_files.append(file_path)
        
        print(f"Успешно скачано {len(downloaded_files)} файлов")
        return downloaded_files