"""Vercel serverless entry point.

Vercel's @vercel/python runtime looks for a top-level WSGI `app` object in
this file. We simply re-export the Flask app defined in backend/app.py.

All routes (/api/health, /api/signals, ...) are already declared on that app,
and vercel.json routes every /api/* request here.
"""
import os
import sys

# Ensure the project root is importable so `backend`, `config`, and `src`
# resolve when Vercel invokes this function.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402  (WSGI app object Vercel serves)

# `app` is the WSGI callable Vercel will serve.
