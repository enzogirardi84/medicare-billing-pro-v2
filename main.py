"""Entry point for Streamlit Cloud - Medicare Billing Pro."""
import sys
import traceback
from pathlib import Path

# Add streamlit_billing to path
billing_path = Path(__file__).resolve().parent / "streamlit_billing"
if str(billing_path) not in sys.path:
    sys.path.insert(0, str(billing_path))

# Import and run the billing app with error handling
try:
    import billing_app
except Exception:
    import streamlit as st
    st.set_page_config(page_title="Error - Medicare Billing Pro")
    st.error("Error al iniciar la app. Detalles:")
    st.code(traceback.format_exc())
    st.stop()
