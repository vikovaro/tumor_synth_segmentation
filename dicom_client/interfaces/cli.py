import click
from typing import Optional
from application.use_cases import (
    DownloadDicomUseCase,
    UploadDicomUseCase,
    ListInstancesUseCase,
    SyncDicomUseCase
)
from application.services import LoggingService, StatisticsService
from infrastructure.orthanc_client import OrthancClient
from infrastructure.file_repository import FileRepository
from domain.entities import DicomInstance


@click.group()
@click.option('--orthanc-url', default='http://localhost:8042',
              help='URL Orthanc сервера')
@click.option('--username', default='orthanc',
              help='Имя пользователя Orthanc')
@click.option('--password', default='orthanc',
              help='Пароль Orthanc')
@click.option('--storage-path', default='./dicom_storage',
              help='Путь к локальному хранилищу')
@click.pass_context
def cli(ctx, orthanc_url, username, password, storage_path):
    """CLI для работы с DICOM файлами через Orthanc REST API"""
    # Инициализируем репозитории
    orthanc_client = OrthancClient()
    orthanc_client.base_url = orthanc_url
    orthanc_client.auth = (username, password)
    
    file_repo = FileRepository(storage_path)
    
    # Инициализируем сервисы
    logging_service = LoggingService()
    stats_service = StatisticsService(file_repo)
    
    # Сохраняем в контексте
    ctx.obj = {
        'orthanc_client': orthanc_client,
        'file_repo': file_repo,
        'logging_service': logging_service,
        'stats_service': stats_service
    }


@cli.command()
@click.argument('instance_id')
@click.pass_context
def download(ctx, instance_id):
    """Скачать DICOM файл по ID инстанса"""
    orthanc_client = ctx.obj['orthanc_client']
    file_repo = ctx.obj['file_repo']
    logging_service = ctx.obj['logging_service']
    
    # Выполняем use case
    use_case = DownloadDicomUseCase(orthanc_client, file_repo)
    result = use_case.execute(instance_id)
    
    # Логируем операцию
    logging_service.log_operation(
        'download',
        'success' if result else 'failed',
        {'instance_id': instance_id, 'result': result}
    )
    
    if result:
        click.echo(f"✅ Файл скачан и сохранен: {result}")
    else:
        click.echo(f"❌ Ошибка при скачивании файла")


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.pass_context
def upload(ctx, file_path):
    """Загрузить DICOM файл на сервер"""
    orthanc_client = ctx.obj['orthanc_client']
    logging_service = ctx.obj['logging_service']
    
    # Выполняем use case
    use_case = UploadDicomUseCase(orthanc_client)
    instance = use_case.execute(file_path)
    
    # Логируем операцию
    logging_service.log_operation(
        'upload',
        'success' if instance else 'failed',
        {'file_path': file_path, 'instance_id': instance.id if instance else None}
    )
    
    if instance:
        click.echo(f"✅ Файл загружен. ID инстанса: {instance.id}")
        click.echo(f"   Пациент: {instance.patient_id}")
        click.echo(f"   Исследование: {instance.study_id}")
        click.echo(f"   Серия: {instance.series_id}")
    else:
        click.echo(f"❌ Ошибка при загрузке файла")


@cli.command()
@click.option('--limit', default=50, help='Максимальное количество инстансов')
@click.pass_context
def list_instances(ctx, limit):
    """Показать список DICOM инстансов на сервере"""
    orthanc_client = ctx.obj['orthanc_client']
    
    # Выполняем use case
    use_case = ListInstancesUseCase(orthanc_client)
    instances = use_case.execute(limit)
    
    click.echo(f"📋 Найдено {len(instances)} инстансов:")
    click.echo("-" * 80)
    
    for instance in instances:
        click.echo(f"ID: {instance.id}")
        click.echo(f"  Пациент: {instance.patient_id}")
        click.echo(f"  Исследование: {instance.study_id}")
        click.echo(f"  Серия: {instance.series_id}")
        if instance.file_size:
            click.echo(f"  Размер: {instance.file_size} байт")
        click.echo()


@cli.command()
@click.option('--limit', default=100, help='Максимальное количество инстансов для синхронизации')
@click.pass_context
def sync(ctx, limit):
    """Синхронизировать все DICOM файлы с сервера"""
    orthanc_client = ctx.obj['orthanc_client']
    file_repo = ctx.obj['file_repo']
    logging_service = ctx.obj['logging_service']
    
    # Выполняем use case
    use_case = SyncDicomUseCase(orthanc_client, file_repo)
    downloaded_files = use_case.execute(limit)
    
    # Логируем операцию
    logging_service.log_operation(
        'sync',
        'success',
        {'downloaded_files': len(downloaded_files), 'limit': limit}
    )
    
    click.echo(f"✅ Синхронизация завершена. Скачано {len(downloaded_files)} файлов")


@cli.command()
@click.pass_context
def stats(ctx):
    """Показать статистику"""
    orthanc_client = ctx.obj['orthanc_client']
    stats_service = ctx.obj['stats_service']
    
    # Статистика сервера
    server_stats = orthanc_client.get_statistics()
    if server_stats:
        click.echo("📊 Статистика сервера:")
        click.echo(f"  Количество пациентов: {server_stats.get('CountPatients', 'N/A')}")
        click.echo(f"  Количество исследований: {server_stats.get('CountStudies', 'N/A')}")
        click.echo(f"  Количество серий: {server_stats.get('CountSeries', 'N/A')}")
        click.echo(f"  Количество инстансов: {server_stats.get('CountInstances', 'N/A')}")
        click.echo()
    
    # Статистика локального хранилища
    local_stats = stats_service.get_storage_statistics()
    click.echo("📁 Статистика локального хранилища:")
    click.echo(f"  Количество пациентов: {local_stats['total_patients']}")
    click.echo(f"  Общий размер: {local_stats['storage_size_mb']:.2f} MB")


@cli.command()
@click.argument('instance_id')
@click.pass_context
def delete(ctx, instance_id):
    """Удалить DICOM инстанс с сервера"""
    orthanc_client = ctx.obj['orthanc_client']
    logging_service = ctx.obj['logging_service']
    
    if click.confirm(f"Вы уверены, что хотите удалить инстанс {instance_id}?"):
        success = orthanc_client.delete_instance(instance_id)
        
        # Логируем операцию
        logging_service.log_operation(
            'delete',
            'success' if success else 'failed',
            {'instance_id': instance_id}
        )
        
        if success:
            click.echo(f"✅ Инстанс {instance_id} удален")
        else:
            click.echo(f"❌ Ошибка при удалении инстанса")


if __name__ == '__main__':
    cli()