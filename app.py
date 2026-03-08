import base64
from pathlib import Path

import streamlit as st

from core.config import init_page, apply_css
from core.db import init_db
from core.auth import require_login
from core.ui import sidebar_controls, sidebar_announcements
from core.excel import build_master_from_uploads

from views.admin import page_admin
from views.ops import page_ops
from views.hr import page_hr
from views.supervision import page_supervision
from views.fleet import page_fleet
from views.accounts import page_accounts
from views.payroll import page_payroll


# =========================
# Assets (support old + new)
# =========================
ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"


def pick_asset(*names: str) -> Path:
    for n in names:
        p = ASSETS / n
        if p.exists():
            return p
    return ASSETS / names[0]


LEFT_IMG = pick_asset("left.jpg", "left.png", "banner.jpg", "banner.png")
RIGHT_IMG = pick_asset("right.jpg", "right.png")
LOGO_IMG = pick_asset("logo.png", "logo.jpg")
FAVICON_IMG = pick_asset("favicon.png", "favicon.jpg", "logo.png", "logo.jpg")


def inject_global_css():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2.4rem !important;
            padding-bottom: 1.5rem !important;
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.4rem !important;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .safeer-subtitle {
            margin-top: -4px;
            opacity: 0.90;
            font-size: 1rem;
        }

        .safeer-title-wrap {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 0.4rem;
        }

        .safeer-logo {
            width: 56px;
            height: 56px;
            border-radius: 14px;
            object-fit: contain;
            background: rgba(255,255,255,0.04);
            padding: 6px;
            border: 1px solid rgba(255,255,255,0.08);
        }

        .safeer-banner {
            width: 100%;
            height: 420px;
            border-radius: 16px;
            overflow: hidden;
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            margin-bottom: 18px;
        }

        @media (max-width: 900px) {
            .safeer-banner { height: 260px; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def render_banner():
    """
    Shows immediately on first open (before login).
    Uses CSS background-image for a full-width rectangular banner.
    """
    if LEFT_IMG.exists():
        data = LEFT_IMG.read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")

        ext = LEFT_IMG.suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"

        st.markdown(
            f"""
            <div class="safeer-banner"
                 style="background-image: url('data:image/{ext};base64,{b64}');">
            </div>
            """,
            unsafe_allow_html=True
        )

    logo_html = ""
    if LOGO_IMG.exists():
        data = LOGO_IMG.read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")
        ext = LOGO_IMG.suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
        logo_html = f'<img class="safeer-logo" src="data:image/{ext};base64,{b64}" alt="Safeer Logo" />'

    st.markdown(
        f"""
        <div class="safeer-title-wrap">
            {logo_html}
            <div>
                <h1 style="margin:0;">لوحة سفير - Safeer Dash</h1>
                <div class="safeer-subtitle">
                    الإدارة / التشغيل / الموارد البشرية / الإشراف / السيارات / الحسابات / مسير الرواتب
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.divider()


def _is_master_df(df) -> bool:
    if df is None:
        return False
    try:
        cols = set(df.columns)
        return ("معرّف السائق" in cols) and ("اسم السائق" in cols)
    except Exception:
        return False


def _is_filtered_df(df) -> bool:
    if df is None:
        return False
    try:
        cols = set(df.columns)
        return ("ترتيب المتابعة" in cols) or ("أولوية" in cols)
    except Exception:
        return False


def _split_master_and_filtered(result):
    """
    Normalize result to: (master_all, filtered_df)
    """
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        return None, None

    a, b = result[0], result[1]

    if _is_filtered_df(a) and _is_master_df(b):
        return b, a
    if _is_master_df(a) and _is_filtered_df(b):
        return a, b

    return b, a


def main():
    try:
        st.set_page_config(
            page_title="Safeer Dash",
            page_icon=str(FAVICON_IMG) if FAVICON_IMG.exists() else "🟢",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass

    init_page()
    inject_global_css()
    apply_css()
    init_db()

    # Show banner before login so first open looks good
    render_banner()

    role = require_login()

    # Main app sidebar tools
    uploaded_files, enabled_files, search, min_delivery, max_cancel = sidebar_controls(role)
    sidebar_announcements(role)

    # Build operational master/filtered data
    result = build_master_from_uploads(enabled_files, search, min_delivery, max_cancel)
    master_all, filtered_df = _split_master_and_filtered(result)

    # Route by role
    if role == "الإدارة":
        try:
            page_admin(master_all, filtered_df)
        except TypeError:
            page_admin(filtered_df)

    elif role == "التشغيل":
        page_ops(master_all, filtered_df)

    elif role == "الموارد البشرية":
        page_hr()

    elif role == "الإشراف":
        try:
            page_supervision(master_all, filtered_df)
        except TypeError:
            page_supervision(filtered_df)

    elif role == "السيارات / الحركة":
        page_fleet()

    elif role == "الحسابات":
        page_accounts()

    elif role == "مسير الرواتب":
        page_payroll(enabled_files)

    else:
        st.info("الدور غير معروف.")


if __name__ == "__main__":
    main()