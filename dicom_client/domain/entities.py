from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class ResourceType(Enum):
    """Типы DICOM ресурсов"""
    PATIENT = "Patient"
    STUDY = "Study"
    SERIES = "Series"
    INSTANCE = "Instance"


@dataclass
class DicomInstance:
    """DICOM инстанс - минимальная единица DICOM данных"""
    id: str
    patient_id: str
    study_id: str
    series_id: str
    instance_number: Optional[int] = None
    sop_instance_uid: Optional[str] = None
    file_size: Optional[int] = None
    file_path: Optional[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DicomSeries:
    """Серия DICOM снимков"""
    id: str
    study_id: str
    series_description: Optional[str] = None
    modality: Optional[str] = None
    instances: List[DicomInstance] = None
    
    def __post_init__(self):
        if self.instances is None:
            self.instances = []


@dataclass
class DicomStudy:
    """Исследование пациента"""
    id: str
    patient_id: str
    study_date: Optional[datetime] = None
    study_description: Optional[str] = None
    series: List[DicomSeries] = None
    
    def __post_init__(self):
        if self.series is None:
            self.series = []


@dataclass
class DicomPatient:
    """Пациент"""
    id: str
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    patient_birth_date: Optional[datetime] = None
    studies: List[DicomStudy] = None
    
    def __post_init__(self):
        if self.studies is None:
            self.studies = []