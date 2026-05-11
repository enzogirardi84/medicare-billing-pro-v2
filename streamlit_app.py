"""Entry point for Streamlit Cloud - Medicare Billing Pro."""
import sys
from pathlib import Path

# Add streamlit_billing to path
billing_path = Path(__file__).resolve().parent / "streamlit_billing"
if str(billing_path) not in sys.path:
    sys.path.insert(0, str(billing_path))

# Import and run the billing app
import billing_app
