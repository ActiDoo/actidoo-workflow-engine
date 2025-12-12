import pathlib

from libcloud.storage.drivers.azure_blobs import AzureBlobsStorageDriver
from libcloud.storage.drivers.local import LocalStorageDriver
from sqlalchemy_file.storage import StorageManager

from actidoo_wfe.settings import Settings


class UnsupportedStorageException(Exception):
    pass

def setup_storage(
    settings: Settings
):
    if settings.storage_mode == 'LOCAL':
        storage_path = pathlib.Path(settings.storage_local_upload_path)
        storage_path.mkdir(exist_ok=True)
        driver = LocalStorageDriver(storage_path)
    elif settings.storage_mode == 'AZURE_BLOB':
        driver = AzureBlobsStorageDriver(
            key=settings.storage_azure_account_name,
            secret=settings.storage_azure_account_key,
            host=settings.storage_azure_override_host,
            port=settings.storage_azure_override_port,
            secure=settings.storage_azure_override_secure,
            **({
                "endpoint_suffix": settings.storage_azure_override_endpoint
            } if settings.storage_azure_override_endpoint else {})
        )
    elif settings.storage_mode == 'AZURE_BLOB_TENANT':
        driver = AzureBlobsStorageDriver(
            key=settings.storage_azure_account_name,
            secret=settings.storage_azure_account_key, # AZURE_CLIENT_SECRET of Service Principal
            tenant_id=settings.storage_azure_tenant_id,
            identity=settings.storage_azure_client_id,
            auth_type="azureAd"
        )
    else:
        raise UnsupportedStorageException()
    
    if "attachment" not in [c.name for c in driver.list_containers()]:
        driver.create_container("attachment")
    StorageManager.add_storage("default", driver.get_container("attachment"))
    
def _unsetup_storage():
    # ONLY for testing purposes
    StorageManager._clear()
    
def get_file_stream(file_id):
    return StorageManager.get_file(f"default/{file_id}").object.as_stream()

def get_file_content(file_id):
    iter = get_file_stream(file_id)
    return b"".join(iter)


