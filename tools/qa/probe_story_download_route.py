"""Diagnose only the initial pinned Hugging Face response, never follow redirects."""
import json
import re
from urllib.parse import urljoin, urlsplit

import requests

from candidates.story_model_manifest import MODEL_ID, PORTABLE_FILES, REVISION

_HOST = re.compile(r"[a-z0-9.-]{1,253}")


def next_host(url, location):
    if not location:
        return None
    try:
        host = urlsplit(urljoin(url, location)).hostname
    except ValueError:
        return None
    return host if host and _HOST.fullmatch(host) else None


def main():
    for name in PORTABLE_FILES:
        url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}"
        result = {"artifact": name, "status": None, "redirect_hostname": None, "identity_encoding": None}
        try:
            with requests.get(url, headers={"Accept-Encoding": "identity"}, stream=True,
                              allow_redirects=False, timeout=(15, 40)) as response:
                result.update(status=response.status_code,
                              redirect_hostname=next_host(url, response.headers.get("Location")),
                              identity_encoding=response.headers.get("Content-Encoding", "identity").lower() == "identity")
        except requests.RequestException:
            result["header_check_failed"] = True
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
