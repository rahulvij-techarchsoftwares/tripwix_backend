import gzip
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("kolo")


def upload_to_dashboard(trace: bytes, upload_key: Optional[str] = None):
    # This should be authed with the upload token optionally..

    base_url = os.environ.get("KOLO_BASE_URL", "https://my.kolo.app")
    url = f"{base_url}/api/traces/"
    payload = gzip.compress(trace)

    if upload_key:
        headers = {"Authorization": f"Bearer {upload_key}"}
    else:
        headers = {}
    return httpx.post(url, headers=headers, files={"data": payload})
