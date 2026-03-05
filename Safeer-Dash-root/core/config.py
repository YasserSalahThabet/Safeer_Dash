from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DATA_DIR = ROOT / "data"
UPLOADS_DIR = ROOT / "uploads"

DB_PATH = DATA_DIR / "safeer_hr.db"

LEFT_IMG = ASSETS / "left.jpg"
RIGHT_IMG = ASSETS / "right.jpg"
LOGO_IMG = ASSETS / "logo.png"
FAVICON_IMG = ASSETS / "favicon.png"


def init_page():
    DATA_DIR.mkdir(exist_ok=True)
    UPLOADS_DIR.mkdir(exist_ok=True)

    st.set_page_config(
        page_title="Safeer Dash",
        page_icon=str(FAVICON_IMG) if FAVICON_IMG.exists() else "🟢",
        layout="wide",
    )


def apply_css():
    # NOTE: Streamlit 1.54 uploader UI customization
    st.markdown(
        """
        <style>
        /* ========== Streamlit 1.54 File Uploader: icon-only button ========== */
        div[data-testid="stFileUploader"] label,
        div[data-testid="stFileUploader"] section div p,
        div[data-testid="stFileUploader"] section small,
        div[data-testid="stFileUploader"] section div span {
            display: none !important;
        }

        div[data-testid="stFileUploader"] section {
            border: 0 !important;
            background: transparent !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        div[data-testid="stFileUploader"] button {
            width: 100% !important;
            border-radius: 12px !important;
            padding: 0.75rem 0.9rem !important;
            font-weight: 800 !important;
            font-size: 16px !important;
            color: transparent !important;
            position: relative;
        }

        div[data-testid="stFileUploader"] button::after {
            content: "📁 تحميل ملفات";
            color: white;
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            white-space: nowrap;
        }

        div[data-testid="stFileUploader"] ul { display: none !important; }

        /* Small polish */
        .block-container { padding-top: 1rem; }
        div[data-testid="stMetric"] { background: rgba(255,255,255,0.02); padding: 8px; border-radius: 12px; }
        div[data-testid="stMetricValue"] { font-size: 19px !important; }
        div[data-testid="stMetricLabel"] { font-size: 11px !important; opacity: 0.8; }
        .safeer-subtitle { margin-top: -10px; opacity: 0.85; }
        </style>
        """,
        unsafe_allow_html=True
    )
