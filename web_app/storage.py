
import os
import uuid
try:
    from minio import Minio
except ImportError:
    Minio = None
    pass
except SyntaxError:
    Minio = None
    pass

from config import Config

class StorageManager:
    def __init__(self):
        self.use_minio = Config.ENABLE_MINIO
        self.upload_folder = Config.UPLOAD_FOLDER
        
        if self.use_minio and Config.MINIO_ENDPOINT and Minio:
            self.client = Minio(
                Config.MINIO_ENDPOINT,
                access_key=Config.MINIO_ACCESS_KEY,
                secret_key=Config.MINIO_SECRET_KEY,
                secure=Config.MINIO_SECURE
            )
            self.bucket = Config.MINIO_BUCKET
            self._ensure_bucket()
        else:
            self.client = None
            if self.use_minio and not Minio:
                print("Warning: MinIO enabled but library not available. Falling back to local.")
            if not os.path.exists(self.upload_folder):
                os.makedirs(self.upload_folder)

    def _ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def save_file(self, file_object, filename):
        """
        Saves a flask file object or byte/string IO.
        """
        if self.use_minio and self.client:
            # IMPORTANT: seek(0) in case it was read
            file_object.seek(0)
            
            # Get size for minio put_object
            try:
                # Flask FileStorage
                file_size = os.fstat(file_object.fileno()).st_size
            except:
                # BytesIO or similar
                file_object.seek(0, os.SEEK_END)
                file_size = file_object.tell()
                file_object.seek(0)
            
            self.client.put_object(
                self.bucket,
                filename,
                file_object,
                file_size
            )
            return filename
        else:
            filepath = os.path.join(self.upload_folder, filename)
            if hasattr(file_object, 'save'):
                file_object.save(filepath)
            else:
                file_object.seek(0)
                with open(filepath, 'wb') as f:
                    f.write(file_object.read())
            return filename

    def get_file_path(self, filename):
        """
        Returns a local path. If using MinIO, downloads to temp first.
        """
        local_path = os.path.join(self.upload_folder, filename)
        
        if self.use_minio and self.client:
            if not os.path.exists(local_path):
                # Download
                try:
                    self.client.fget_object(self.bucket, filename, local_path)
                except Exception as e:
                    print("File not found in MinIO: {}".format(e))
                    return None
        
        if os.path.exists(local_path):
            return local_path
        return None

    def exists(self, filename):
        if self.use_minio and self.client:
             try:
                 self.client.stat_object(self.bucket, filename)
                 return True
             except:
                 return False
        else:
            return os.path.exists(os.path.join(self.upload_folder, filename))

    def delete(self, filename):
        if self.use_minio and self.client:
            self.client.remove_object(self.bucket, filename)
            # Also clean local cache if needed
            local = os.path.join(self.upload_folder, filename)
            if os.path.exists(local):
                os.remove(local)
        else:
            p = os.path.join(self.upload_folder, filename)
            if os.path.exists(p):
                os.remove(p)

storage = StorageManager()
