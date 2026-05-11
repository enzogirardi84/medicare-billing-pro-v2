"""Dual entry point for API tests and Streamlit Cloud."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from api_main import app  # FastAPI app expected by the API test suite.


def _run_streamlit_app() -> None:
    billing_path = Path(__file__).resolve().parent / "streamlit_billing"
    if str(billing_path) not in sys.path:
        sys.path.insert(0, str(billing_path))
    try:
        import billing_app

        billing_app.run_app()
    except Exception:
        import streamlit as st

        try:
            st.set_page_config(page_title="Error - Medicare Billing Pro")
        except Exception:
            pass
        st.error("Error al iniciar la app. Detalles:")
        st.code(traceback.format_exc())
        st.stop()


if "pytest" not in sys.modules:
    _run_streamlit_app()
