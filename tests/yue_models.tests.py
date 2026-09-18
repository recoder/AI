"""HTTP boundary tests using a local range-capable server; no model/GPU downloads."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("yue_models", Path(__file__).resolve().parents[1] / "tools/yue/models.py")
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)


class Download(unittest.TestCase):
    def test_range_resume_and_hash_verification(self):
        payload = bytes(range(256)) * 32
        ranges = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                start, end = map(int, self.headers["Range"].split("=")[1].split("-"))
                ranges.append((start, end))
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
                self.send_header("Content-Length", str(end - start + 1))
                self.end_headers()
                self.wfile.write(payload[start:end + 1])
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary)
                revision = "a" * 40
                artifact = dict(name="weights.dat", size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                partial = destination / ("weights.dat." + revision + ".partial")
                partial.write_bytes(payload[:257])
                with patch("huggingface_hub.hf_hub_url", return_value=f"http://127.0.0.1:{server.server_port}/artifact"):
                    models.download_http(dict(repo="fixture/model", revision=revision, chunk_bytes=1024), artifact, destination)
                self.assertEqual(ranges[0][0], 257)
                self.assertEqual((destination / "weights.dat").read_bytes(), payload)
                self.assertFalse(partial.exists())
                self.assertTrue(models.check(destination / "weights.dat", artifact))
                (destination / "weights.dat").write_bytes(bytes(len(payload)))
                self.assertFalse(models.check(destination / "weights.dat", artifact))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_wrong_range_does_not_append_or_replace(self):
        response = unittest.mock.MagicMock()
        response.status_code = 206
        response.headers = {"Content-Range": "bytes 0-1023/2048"}
        response.__enter__.return_value = response
        session = unittest.mock.MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = response
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            revision = "a" * 40
            partial = destination / ("weights.dat." + revision + ".partial")
            partial.write_bytes(b"existing")
            with patch("requests.Session", return_value=session), self.assertRaises(RuntimeError):
                models.download_http(dict(repo="fixture/model", revision=revision, chunk_bytes=1024), dict(name="weights.dat", size=2048), destination)
            self.assertEqual(partial.read_bytes(), b"existing")
            self.assertFalse((destination / "weights.dat").exists())


if __name__ == "__main__":
    unittest.main()
