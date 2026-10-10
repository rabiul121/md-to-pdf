import functools
import http.server
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from src import converter
from src.core import engine
from src.core import images


def sample_png():
    """Create a valid RGB PNG without adding an imaging dependency."""
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">2I5B", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\x00\xff\x00" * 2))
            + chunk(b"IEND", b""))


class ImageRenderingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("pandoc"), "Pandoc is required")
    def test_remote_image_preparation_preserves_references_and_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.md"
            source.write_text(
                "![One][image]\n\n![Two][image]\n\n"
                "[image]: https://example.com/image?purpose=inline\n\n"
                "`![Code](https://example.com/code)`\n\n**bold**",
                encoding="utf-8",
            )
            local = root / "image.png"
            local.write_bytes(sample_png())
            with patch.object(images, "download_image", return_value=local) as download:
                prepared = images.prepare_remote_images(source, "pandoc", root, lambda _message: None)
            download.assert_called_once()
            document = prepared.read_text(encoding="utf-8")
            self.assertEqual(document.count(local.as_posix()), 2)
            self.assertIn('"Strong"', document)
            self.assertIn("https://example.com/code", document)

    @unittest.skipUnless(shutil.which("pandoc"), "Pandoc is required")
    def test_failed_download_keeps_description_and_logs_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.md"
            source.write_text("![Description](https://example.com/missing)", encoding="utf-8")
            logs = []
            with patch.object(images, "download_image", side_effect=OSError("connection refused")):
                prepared = images.prepare_remote_images(source, "pandoc", root, logs.append)
            document = json.loads(prepared.read_text(encoding="utf-8"))
            self.assertNotIn('"Image"', json.dumps(document))
            self.assertIn("Description", json.dumps(document))
            self.assertIn("connection refused", logs[0])

    def test_both_entry_points_resolve_resources_and_show_warnings(self):
        warning = "[WARNING] Could not fetch resource missing.png: replacing image with description"
        for module in (engine, converter):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "source.md"
                source.write_text("![Missing](missing.png)", encoding="utf-8")
                logs = []
                with patch.object(module, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                    module, "font_file_supports_codepoint", return_value=False
                ), patch.object(
                    module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", warning)
                ) as run:
                    success, _ = module.convert_md_to_pdf(
                        source, output_directory=root, include_toc=False, log_func=logs.append,
                    )
                self.assertTrue(success)
                resource_argument = next(
                    arg for arg in run.call_args.args[0] if arg.startswith("--resource-path=")
                )
                self.assertEqual(resource_argument.split("=", 1)[1].split(os.pathsep)[0], str(root))
                self.assertIn(warning, logs)

    @unittest.skipUnless(
        shutil.which("pandoc") and shutil.which("xelatex"),
        "Pandoc and XeLaTeX are required",
    )
    def test_pdf_contains_relative_absolute_and_remote_images(self):
        with tempfile.TemporaryDirectory(prefix="image rendering ") as directory:
            root = Path(directory)
            assets = root / "images"
            assets.mkdir()
            image = assets / "sample.png"
            image.write_bytes(sample_png())
            class BrowserHeadersHandler(http.server.SimpleHTTPRequestHandler):
                def do_GET(self):
                    if self.headers.get("User-Agent") != "Mozilla/5.0":
                        self.send_error(403, "Browser-style headers required")
                        return
                    super().do_GET()

            handler = functools.partial(BrowserHeadersHandler, directory=str(root))
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                remote = f"http://127.0.0.1:{server.server_port}/images/sample.png?purpose=inline"
                source = root / "source.md"
                source.write_text(
                    "Before **bold**\n\n![Relative](images/sample.png)\n\n"
                    f"![Absolute](<{image.as_posix()}>)\n\n![Remote]({remote})\n\nAfter",
                    encoding="utf-8",
                )
                for module in (engine, converter):
                    with self.subTest(module=module.__name__):
                        logs = []
                        # Keep the local fixture server out of system HTTP proxies.
                        with patch.dict(os.environ, {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}):
                            success, output = module.convert_md_to_pdf(
                                source, output_directory=root, include_toc=False, log_func=logs.append,
                            )
                        self.assertTrue(success, output)
                        self.assertFalse(any("Could not fetch resource" in line for line in logs), logs)
                        self.assertIn("[IMAGE] Downloaded remote image", logs)
                        self.assertTrue(
                            re.search(rb"/Subtype\s*/Image\b", Path(output).read_bytes()),
                            "The generated PDF must contain an image object",
                        )
                        if shutil.which("pdftotext"):
                            text = subprocess.run(
                                ["pdftotext", output, "-"], capture_output=True,
                                text=True, encoding="utf-8", check=True,
                            ).stdout
                            for caption in ("Relative", "Absolute", "Remote"):
                                self.assertIn(caption, text)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()