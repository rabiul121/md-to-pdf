"""Download remote Markdown images before Pandoc's PDF resource handling."""

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path


def download_image(url, directory):
    """Use system proxy settings and verified TLS with browser-style headers."""
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(25 * 1024 * 1024 + 1)
    if len(data) > 25 * 1024 * 1024:
        raise ValueError("Image exceeds the 25 MB download limit")
    if data.startswith(b"\xff\xd8\xff"):
        extension = ".jpg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = ".png"
    elif data.startswith(b"%PDF-"):
        extension = ".pdf"
    else:
        raise ValueError("The URL did not return a supported PNG, JPEG, or PDF image")
    target = Path(directory) / (hashlib.sha256(url.encode("utf-8")).hexdigest() + extension)
    target.write_bytes(data)
    return target


def prepare_remote_images(source, pandoc, directory, log_func):
    """Return a JSON document with local image targets, or the original source.

    Pandoc parses the Markdown so reference images, escaped URLs, captions,
    and code blocks retain their proper semantics. Only Image nodes change.
    """
    if source.suffix.lower() not in {".md", ".markdown", ".txt"}:
        return source
    text = source.read_text(encoding="utf-8-sig")
    if "http://" not in text and "https://" not in text:
        return source
    result = subprocess.run(
        [pandoc, str(source), "--from=markdown", "--to=json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    document = json.loads(result.stdout)
    downloads = {}

    def visit(node):
        if isinstance(node, list):
            for index, child in enumerate(node):
                node[index] = visit(child)
        elif isinstance(node, dict):
            if node.get("t") == "Image":
                url = node["c"][2][0]
                if url.startswith(("https://", "http://")):
                    if url not in downloads:
                        try:
                            downloads[url] = download_image(url, directory).as_posix()
                            log_func("[IMAGE] Downloaded remote image")
                        except Exception as error:
                            downloads[url] = None
                            log_func(f"[WARNING] Could not download image {url}: {error}")
                    if downloads[url]:
                        node["c"][2][0] = downloads[url]
                    else:
                        # Avoid a second failing request through Pandoc's client.
                        return {"t": "Span", "c": [node["c"][0], node["c"][1]]}
            for key, child in node.items():
                node[key] = visit(child)
        return node

    visit(document)
    if not downloads:
        return source
    target = Path(directory) / "document.json"
    target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return target