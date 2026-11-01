"""A nyers fájlok Garage-ba írása."""

import boto3
from botocore.config import Config

BUCKET = "raw"
EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/heic": "heic",
    "image/webp": "webp",
    "application/pdf": "pdf",
}


class Storage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str):
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="garage",
            config=Config(
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 2},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=BUCKET, Key=key, Body=content, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
