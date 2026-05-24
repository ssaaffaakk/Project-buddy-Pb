"""
File Storage Service

Abstracts local disk vs. S3 (or S3-compatible) object storage.

Configuration (via environment variables):
    AWS_S3_BUCKET       — bucket name; if unset, local disk is used
    AWS_S3_REGION       — e.g. "eu-central-1"  (default: us-east-1)
    AWS_ACCESS_KEY_ID   — IAM key
    AWS_SECRET_ACCESS_KEY
    AWS_S3_ENDPOINT_URL — optional; for S3-compatible services (e.g. Backblaze, MinIO)
    AWS_CLOUDFRONT_URL  — optional; if set, returned URLs use this CDN prefix
                          instead of the S3 bucket URL

Usage:
    from services.file_storage import storage

    url = storage.save(file_bytes, "avatar.webp", category="avatars")
    # returns "/static/uploads/avatars/avatar.webp"  (local)
    # or      "https://cdn.example.com/avatars/avatar.webp"  (S3/CDN)

    storage.delete(url)

    # For file downloads (study groups):
    redirect_url = storage.download_url("avatars/avatar.webp")
    # local → None  (caller uses send_from_directory)
    # S3    → pre-signed URL string
"""

import os
import logging

logger = logging.getLogger(__name__)


class LocalStorage:
    """Saves files to static/uploads/<category>/."""

    def __init__(self, base_path: str):
        self.base_path = base_path  # absolute path to static/uploads

    def save(self, data: bytes, filename: str, category: str) -> str:
        dest_dir = os.path.join(self.base_path, category)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        with open(dest, "wb") as f:
            f.write(data)
        return f"/static/uploads/{category}/{filename}"

    def delete(self, url: str) -> None:
        # url looks like /static/uploads/avatars/foo.webp
        rel = url.lstrip("/")          # static/uploads/avatars/foo.webp
        # base_path is <root>/static/uploads  →  root is two levels up
        root = os.path.dirname(os.path.dirname(self.base_path))
        full = os.path.join(root, rel)
        if os.path.exists(full):
            os.remove(full)

    def download_url(self, key: str):
        """Local storage: caller should use send_from_directory. Return None."""
        return None

    def local_path(self, category: str, stored_name: str) -> str:
        """Return the absolute local path for send_from_directory."""
        return os.path.join(self.base_path, category)


class S3Storage:
    """Uploads files to AWS S3 (or compatible) and returns public/CDN URLs."""

    def __init__(self):
        import boto3
        self.bucket      = os.environ["AWS_S3_BUCKET"]
        self.region      = os.environ.get("AWS_S3_REGION", "us-east-1")
        self.cdn_url     = os.environ.get("AWS_CLOUDFRONT_URL", "").rstrip("/")
        endpoint_url     = os.environ.get("AWS_ENDPOINT_URL") or None

        self.client = boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=endpoint_url,
        )

    def _key(self, category: str, filename: str) -> str:
        return f"{category}/{filename}"

    def save(self, data: bytes, filename: str, category: str) -> str:
        key = self._key(category, filename)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=_guess_content_type(filename),
        )
        if self.cdn_url:
            return f"{self.cdn_url}/{key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def delete(self, url: str) -> None:
        # Extract key from URL
        if self.cdn_url and url.startswith(self.cdn_url):
            key = url[len(self.cdn_url):].lstrip("/")
        else:
            # https://bucket.s3.region.amazonaws.com/key
            key = "/".join(url.split("/")[3:])
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as e:
            logger.warning("S3 delete failed for key %s: %s", key, e)

    def download_url(self, key: str, expiry: int = 3600) -> str:
        """Return a pre-signed download URL valid for `expiry` seconds."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expiry,
        )

    def local_path(self, category: str, stored_name: str):
        """S3 has no local path — caller should use download_url instead."""
        return None


def _guess_content_type(filename: str) -> str:
    import mimetypes
    ct, _ = mimetypes.guess_type(filename)
    return ct or "application/octet-stream"


def _build_storage() -> LocalStorage | S3Storage:
    if os.environ.get("AWS_S3_BUCKET"):
        try:
            s = S3Storage()
            logger.info("File storage: S3 bucket '%s'", s.bucket)
            return s
        except Exception as e:
            logger.warning("S3 init failed (%s), falling back to local storage.", e)
    # Fallback: local disk
    # __file__ is services/file_storage.py → project root is one level up
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_path = os.path.join(project_root, "static", "uploads")
    logger.info("File storage: local disk at %s", base_path)
    return LocalStorage(base_path)


# Module-level singleton — imported by routes
storage = _build_storage()
