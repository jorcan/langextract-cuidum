#!/usr/bin/env python3
"""Sirve el panel de observabilidad Langextract SOLO en localhost (127.0.0.1:8651).

Sin exposición a internet: bind explícito a loopback. El acceso es vía túnel
SSH (`ssh -N -L 8651:127.0.0.1:8651 <host>`), la autenticación es tu clave SSH.
"""
import http.server
import logging
import os
from pathlib import Path

HOST = "127.0.0.1"          # SOLO loopback — nunca 0.0.0.0
PORT = int(os.environ.get("OBS_LANGEXTRACT_PORT", 8651))
DIR = Path.home() / ".hermes" / "obs"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("obs-serve")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Sirve archivos del dir privado; log mínimo (sin volcar rutas sensibles)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR), **kwargs)

    def log_message(self, fmt, *args):
        logger.info("%s %s", self.address_string(), fmt % args)


def main():
    DIR.mkdir(parents=True, exist_ok=True)
    httpd = http.server.ThreadingHTTPServer((HOST, PORT), QuietHandler)
    logger.info("Sirviendo %s en http://%s:%d (solo loopback; usa túnel SSH)", DIR, HOST, PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()