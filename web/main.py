"""PyScript entry point. All code lives in the ``kvale_web`` package."""

from kvale_web.app import start

await start()  # noqa: F704, PLE1142  (PyScript runs this file with top-level await)
