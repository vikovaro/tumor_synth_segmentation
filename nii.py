import os
import pydicom
import nibabel as nib
import numpy as np
import json
from glob import glob
from tqdm import tqdm
import gzip
import shutil
from datetime import datetime
import re

class DICOMtoNIIConverter:
    def __init__(self, base_path):
        self.base_path = base_path
        self.scan_types_info = {
            'T1': {'keywords': ['t1', 't1_', 't1w', 't1-w', 'mprage', 'bravo', 'spgr'],
                   'TE_range': (2, 30), 'TR_range': (300, 800)},
            'T1-CE': {'keywords': ['t1', 't1_', 't1w', '+c', 'contrast', 'ce', 'post'],
                      'TE_range': (2, 30), 'TR_range': (300, 800)},
            'T2': {'keywords': ['t2', 't2_', 't2w', 't2-w', 'tse', 'haste'],
                   'TE_range': (80, 150), 'TR_range': (2000, 6000)},
            'FLAIR': {'keywords': ['flair', 'fluid', 'dark fluid'],
                      'TE_range': (80, 150), 'TR_range': (8000, 12000)},
            'DWI': {'keywords': ['dwi', 'diffusion'],
                    'TE_range': (50, 100), 'TR_range': (3000, 8000)},
            'ADC': {'keywords': ['adc'], 'TE_range': (50, 100), 'TR_range': (3000, 8000)}
        }
    
    def safe_filename(self, filename, max_length=200):
        """Создание безопасного имени файла для Windows"""
        # Удаляем недопустимые символы
        invalid_chars = r'[<>:"/\\|?*:\-><]'
        filename = re.sub(invalid_chars, '_', filename)
        
        # Удаляем непечатаемые символы
        filename = ''.join(char for char in filename if char.isprintable())
        
        # Заменяем множественные пробелы и подчеркивания
        filename = re.sub(r'\s+', '_', filename)
        filename = re.sub(r'_+', '_', filename)
        
        # Обрезаем до максимальной длины
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            # Оставляем расширение и обрезаем имя
            if len(ext) < max_length - 10:
                filename = name[:max_length - len(ext)] + ext
            else:
                filename = filename[:max_length]
        
        # Убедимся, что имя не пустое
        if not filename.strip('._ '):
            filename = f"series_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return filename.strip('._ ')
    
    def extract_dicom_metadata(self, dcm_file):
        """Извлечение метаданных из DICOM файла"""
        try:
            ds = pydicom.dcmread(dcm_file, stop_before_pixels=True, force=True)
            
            # Безопасное извлечение текстовых полей
            def safe_get(field, default=''):
                try:
                    value = ds.get(field, default)
                    if value is None:
                        return default
                    return str(value).lower().strip()
                except:
                    return default
            
            metadata = {
                'SeriesDescription': safe_get('SeriesDescription'),
                'ProtocolName': safe_get('ProtocolName'),
                'SequenceName': safe_get('SequenceName'),
                'ScanOptions': safe_get('ScanOptions'),
                'MRAcquisitionType': safe_get('MRAcquisitionType'),
                'EchoTime': float(ds.get('EchoTime', 0)) if ds.get('EchoTime') else 0,
                'RepetitionTime': float(ds.get('RepetitionTime', 0)) if ds.get('RepetitionTime') else 0,
                'InversionTime': float(ds.get('InversionTime', 0)) if ds.get('InversionTime') else 0,
                'ContrastBolusAgent': safe_get('ContrastBolusAgent'),
                'ImageType': safe_get('ImageType'),
                'Modality': safe_get('Modality'),
                'SeriesNumber': int(ds.get('SeriesNumber', 0)),
                'InstanceNumber': int(ds.get('InstanceNumber', 0)),
                'SliceThickness': float(ds.get('SliceThickness', 0)) if ds.get('SliceThickness') else 0,
                'PixelSpacing': ds.get('PixelSpacing', [1, 1]),
                'PatientID': safe_get('PatientID'),
                'StudyDate': safe_get('StudyDate'),
                'PatientName': safe_get('PatientName')
            }
            return metadata
        except Exception as e:
            print(f"Ошибка чтения {dcm_file}: {e}")
            return None
    
    def determine_scan_type(self, metadata, dcm_files_sample):
        """Определение типа скана по метаданным"""
        if not metadata:
            return "Unknown"
        
        series_desc = metadata['SeriesDescription']
        protocol = metadata['ProtocolName']
        
        # Проверка на контраст
        has_contrast = any([
            '+c' in series_desc,
            'contrast' in series_desc,
            'ce' in series_desc,
            'post' in series_desc,
            'gd' in series_desc,
            metadata['ContrastBolusAgent'] != ''
        ])
        
        # Список всех текстовых полей для поиска ключевых слов
        text_fields = [
            series_desc,
            protocol,
            metadata['SequenceName'],
            metadata['ScanOptions']
        ]
        
        text_combined = ' '.join(text_fields)
        
        # Определение по ключевым словам
        for scan_type, info in self.scan_types_info.items():
            for keyword in info['keywords']:
                if keyword in text_combined:
                    # Особый случай для T1 с контрастом
                    if scan_type == 'T1' and has_contrast:
                        return 'T1-CE'
                    return scan_type
        
        # Определение по временным параметрам (если доступны)
        te, tr = metadata['EchoTime'], metadata['RepetitionTime']
        
        if te > 0 and tr > 0:
            for scan_type, info in self.scan_types_info.items():
                if (info['TE_range'][0] <= te <= info['TE_range'][1] and 
                    info['TR_range'][0] <= tr <= info['TR_range'][1]):
                    if scan_type == 'T1' and has_contrast:
                        return 'T1-CE'
                    return scan_type
        
        # Дополнительная эвристика для конкретного случая
        if 'mpr' in text_combined or 'multiplanar' in text_combined:
            if 't1' in text_combined:
                return 'T1-MPR'
            elif 't2' in text_combined:
                return 'T2-MPR'
            else:
                return 'MPR'
        
        return "Unknown"
    
    def find_dicom_series(self, folder):
        """Поиск всех серий DICOM в папке и подпапках"""
        dicom_series = {}
        
        # Рекурсивный поиск .dcm файлов
        dcm_files = []
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(('.dcm', '.dicom', '.ima')):
                    dcm_files.append(os.path.join(root, file))
        
        print(f"Найдено {len(dcm_files)} DICOM файлов")
        
        # Группировка по сериям (используем все файлы для точности)
        for dcm_file in tqdm(dcm_files[:min(500, len(dcm_files))], desc="Анализ серий"):
            metadata = self.extract_dicom_metadata(dcm_file)
            if metadata:
                series_num = metadata.get('SeriesNumber', 0)
                series_key = f"{series_num:04d}_{metadata.get('SeriesDescription', 'Unknown')[:50]}"
                
                if series_key not in dicom_series:
                    dicom_series[series_key] = {
                        'files': [],
                        'metadata': metadata,
                        'sample_file': dcm_file
                    }
                
                dicom_series[series_key]['files'].append(dcm_file)
        
        return dicom_series
    
    def sort_dicom_slices(self, filepaths):
        """Сортировка DICOM срезов по позиции"""
        slices_info = []
        
        for filepath in filepaths:
            try:
                ds = pydicom.dcmread(filepath, stop_before_pixels=False, force=True)
                instance_num = ds.get('InstanceNumber', 0)
                
                # Используем разные методы определения позиции
                if hasattr(ds, 'SliceLocation'):
                    slice_pos = ds.SliceLocation
                elif hasattr(ds, 'ImagePositionPatient'):
                    slice_pos = ds.ImagePositionPatient[2]
                else:
                    slice_pos = instance_num
                
                slices_info.append((slice_pos, instance_num, filepath, ds))
            except Exception as e:
                print(f"Ошибка чтения {filepath}: {e}")
                continue
        
        # Сортировка по позиции среза
        slices_info.sort(key=lambda x: (float(x[0]), x[1]))
        
        return slices_info
    
    def convert_series_to_nifti(self, series_info, output_dir, patient_id):
        """Конвертация одной серии в NIfTI"""
        if not series_info['files']:
            print("Нет файлов для конвертации")
            return None
        
        try:
            # Определение типа скана
            scan_type = self.determine_scan_type(
                series_info['metadata'], 
                series_info['files'][:5]
            )
            
            print(f"  Тип определен как: {scan_type}")
            
            # Сортировка срезов
            sorted_slices = self.sort_dicom_slices(series_info['files'])
            
            if not sorted_slices:
                print("  Не удалось отсортировать срезы")
                return None
            
            print(f"  Отсортировано {len(sorted_slices)} срезов")
            
            # Проверяем размеры
            first_ds = sorted_slices[0][3]
            first_shape = first_ds.pixel_array.shape
            consistent = all(s[3].pixel_array.shape == first_shape for s in sorted_slices)
            
            if not consistent:
                print("  Предупреждение: размеры срезов различаются")
            
            # Создание 3D массива
            slice_data = []
            
            for _, _, filepath, ds in sorted_slices:
                pixel_array = ds.pixel_array
                
                # Преобразование HU для CT
                if ds.get('Modality') == 'CT':
                    if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                        pixel_array = pixel_array * ds.RescaleSlope + ds.RescaleIntercept
                
                slice_data.append(pixel_array)
            
            # Создание 3D массива
            volume = np.stack(slice_data, axis=-1)
            print(f"  Создан объем размером: {volume.shape}")
            
            # Создание affine матрицы
            ds_sample = sorted_slices[0][3]
            pixel_spacing = ds_sample.get('PixelSpacing', [1.0, 1.0])
            slice_thickness = ds_sample.get('SliceThickness', 1.0)
            
            affine = np.eye(4)
            affine[0, 0] = float(pixel_spacing[0]) if len(pixel_spacing) > 0 else 1.0
            affine[1, 1] = float(pixel_spacing[1]) if len(pixel_spacing) > 1 else 1.0
            affine[2, 2] = float(slice_thickness)
            
            # Создание NIfTI изображения
            nii_img = nib.Nifti1Image(volume, affine)
            
            # Формирование безопасного имени файла
            series_desc = series_info['metadata']['SeriesDescription']
            series_num = series_info['metadata']['SeriesNumber']
            
            # Создаем простое имя файла
            safe_patient_id = self.safe_filename(patient_id[:20])
            safe_series_desc = self.safe_filename(series_desc[:30])
            
            filename = f"{safe_patient_id}_{scan_type}_S{series_num}_{safe_series_desc}.nii.gz"
            filepath = os.path.join(output_dir, filename)
            
            # Сохраняем напрямую в .nii.gz
            nib.save(nii_img, filepath.replace('.gz', ''))
            
            # Сжатие в .gz
            with open(filepath.replace('.gz', ''), 'rb') as f_in:
                with gzip.open(filepath, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Удаляем временный файл
            os.remove(filepath.replace('.gz', ''))
            
            print(f"  Сохранено: {filename}")
            
            return {
                'filename': filename,
                'scan_type': scan_type,
                'series_number': series_num,
                'shape': volume.shape,
                'original_files': len(series_info['files']),
                'voxel_size': [affine[0, 0], affine[1, 1], affine[2, 2]]
            }
            
        except Exception as e:
            print(f"  Ошибка при конвертации: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_all_series(self, input_dir=None, output_dir=None):
        """Основная функция обработки всех серий"""
        if input_dir is None:
            input_dir = self.base_path
        if output_dir is None:
            # Создаем выходную папку рядом с исходной
            output_dir = os.path.join(os.path.dirname(input_dir), 'nifti_output')
        
        # Создаем безопасный путь
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Входная папка: {input_dir}")
        print(f"Выходная папка: {output_dir}")
        
        # Поиск всех серий
        print("Поиск DICOM серий...")
        dicom_series = self.find_dicom_series(input_dir)
        
        print(f"Найдено {len(dicom_series)} серий")
        
        # Конвертация каждой серии
        results = []
        summary = {}
        
        for series_key, series_info in dicom_series.items():
            print(f"\n{'='*60}")
            print(f"Обработка серии: {series_key}")
            
            # Получаем PatientID из метаданных
            patient_id = series_info['metadata'].get('PatientID', 'Unknown')
            if patient_id == '' or patient_id == 'unknown':
                # Пробуем получить из имени файла или папки
                sample_path = series_info['sample_file']
                folder_name = os.path.basename(os.path.dirname(os.path.dirname(sample_path)))
                patient_id = folder_name if folder_name else f"Patient_{datetime.now().strftime('%Y%m%d')}"
            
            result = self.convert_series_to_nifti(series_info, output_dir, patient_id)
            
            if result:
                results.append(result)
                scan_type = result['scan_type']
                if scan_type not in summary:
                    summary[scan_type] = 0
                summary[scan_type] += 1
            else:
                print(f"  Не удалось конвертировать серию {series_key}")
        
        # Сохранение отчета
        self.save_report(results, output_dir, summary)
        
        return results
    
    def save_report(self, results, output_dir, summary):
        """Сохранение отчета о конвертации"""
        report_path = os.path.join(output_dir, 'conversion_report.json')
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_series': len(results),
            'summary_by_type': summary,
            'details': results
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print("ОТЧЕТ О КОНВЕРТАЦИИ:")
        print(f"Всего серий: {len(results)}")
        for scan_type, count in summary.items():
            print(f"  {scan_type}: {count} серий")
        print(f"Результаты сохранены в: {output_dir}")
        print(f"Отчет: {report_path}")
        print('='*60)


# Упрощенная версия для отладки
def simple_converter():
    """Простой конвертер для быстрой диагностики"""
    import pydicom
    import nibabel as nib
    import numpy as np
    import os
    from glob import glob
    
    # Укажите путь к вашим файлам
    dicom_folder = r"D:\RUDN\tumor\P0008\P0008\Head_Biobank - 3937\TraceJan_24_2023_091256_950"
    
    # Находим все DICOM файлы
    dicom_files = []
    for root, dirs, files in os.walk(dicom_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                dicom_files.append(os.path.join(root, file))
    
    print(f"Найдено {len(dicom_files)} файлов")
    
    if not dicom_files:
        print("Файлы не найдены! Проверьте путь.")
        return
    
    # Берем первые 10 файлов для теста
    test_files = dicom_files[:10]
    
    # Читаем и анализируем
    for i, file_path in enumerate(test_files):
        print(f"\nФайл {i+1}: {os.path.basename(file_path)}")
        try:
            ds = pydicom.dcmread(file_path, stop_before_pixels=True)
            print(f"  Series Description: {ds.get('SeriesDescription', 'N/A')}")
            print(f"  Series Number: {ds.get('SeriesNumber', 'N/A')}")
            print(f"  Modality: {ds.get('Modality', 'N/A')}")
            print(f"  Echo Time: {ds.get('EchoTime', 'N/A')}")
            print(f"  Repetition Time: {ds.get('RepetitionTime', 'N/A')}")
        except Exception as e:
            print(f"  Ошибка: {e}")

# Основной запуск
if __name__ == "__main__":
    print("DICOM to NIfTI Converter для Windows")
    print("=" * 50)
    
    # Тестовый запуск для диагностики
    # simple_converter()
    
    # Полная обработка
    input_directory = r"D:\RUDN\tumor\P0008\P0008\Head_Biobank - 3937\TraceJan_24_2023_091256_950"
    
    # Создание конвертера и запуск обработки
    converter = DICOMtoNIIConverter(input_directory)
    
    # Обработка всех файлов
    try:
        results = converter.process_all_series()
        if not results:
            print("\nНет результатов конвертации. Возможные причины:")
            print("1. Файлы не найдены в указанной папке")
            print("2. Формат файлов не поддерживается")
            print("3. Ошибки при чтении DICOM файлов")
            print("\nЗапустите simple_converter() для диагностики")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        import traceback
        traceback.print_exc()