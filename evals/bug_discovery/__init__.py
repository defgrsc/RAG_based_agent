"""Automatic scenario-based bug discovery pipeline."""

import os


os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
os.environ.setdefault("CONFIDENT_TRACING_ENABLED", "NO")

__version__ = "0.1.0"
