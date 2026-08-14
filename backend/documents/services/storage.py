from functools import lru_cache

import boto3
from botocore.client import Config
from django.conf import settings


@lru_cache(maxsize=1)
def get_s3_client():
    scheme = "https" if settings.MINIO_USE_SSL else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket():
    client = get_s3_client()
    existing = [b["Name"] for b in client.list_buckets()["Buckets"]]
    if settings.MINIO_BUCKET not in existing:
        client.create_bucket(Bucket=settings.MINIO_BUCKET)


def generate_upload_url(key, content_type, expires_in=600):
    ensure_bucket()
    client = get_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.MINIO_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_in,
    )


def generate_download_url(key, filename, expires_in=600):
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.MINIO_BUCKET,
            "Key": key,
            "ResponseContentDisposition": f'inline; filename="{filename}"',
            "ResponseContentType": "application/pdf",
        },
        ExpiresIn=expires_in,
    )


def head_object(key):
    client = get_s3_client()
    return client.head_object(Bucket=settings.MINIO_BUCKET, Key=key)


def get_object_bytes(key):
    client = get_s3_client()
    obj = client.get_object(Bucket=settings.MINIO_BUCKET, Key=key)
    return obj["Body"].read()


def delete_object(key):
    client = get_s3_client()
    client.delete_object(Bucket=settings.MINIO_BUCKET, Key=key)
