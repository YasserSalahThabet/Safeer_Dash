import streamlit as st
from pathlib import Path

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
FAVICON_IMG = pick_asset("favicon.png", "favicon.jpg")


def inject_global_css():
    st.markdown(
        """
        <style>
        /* prevent top crop */
        .block-container { padding-top: 1.2rem !important; }

        section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }

        /* hide streamlit chrome */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        .safeer-subtitle { margin-top: -10px; opacity: 0.85; }

        /* Full-width banner */
        .safeer-banner {
            width: 100%;
            height: 320px;           /* adjust if you want taller */
            border-radius: 16px;
            overflow: hidden;
            background-position: center;
            background-size: cover;  /* this makes it fill width nicely */
            background-repeat: no-repeat;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            margin-bottom: 16px;
        }

        @media (max-width: 900px) {
            .safeer-banner { height: 220px; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def render_banner():
    """
    Shows immediately on first open (before login).
    Uses CSS background-image to force a full-width rectangular banner.
    """
    if LEFT_IMG.exists():
        # Streamlit needs a URL it can serve; st.image gives that, but we want background-cover.
        # We'll read bytes and embed as data URL.
        import base64
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

    st.markdown("# لوحة سفير - Safeer Dash")
    st.markdown(
        '<div class="safeer-subtitle">الإدارة / التشغيل / الموارد البشرية / الإشراف / السيارات / الحسابات / مسير الرواتب</div>',
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
    Normalize result to: (master_all, f)
    """
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        return None, None

    a, b = result[0], result[1]

    if _is_filtered_df(a) and _is_master_df(b):
        return b, a
    if _is_master_df(a) and _is_filtered_df(b):
        return a, b

    # fallback
    return b, a


def main():
    try:
        st.set_page_config(
            page_title="Safeer Dash",
            page_icon=str(FAVICON_IMG) if FAVICON_IMG.exists() else "🟢",
            layout="wide",
        )
    except Exception:
        pass

    init_page()
    inject_global_css()
    apply_css()
    init_db()

    # ✅ IMPORTANT: show banner BEFORE login so it appears on first open
    render_banner()

    # Login (this may st.stop() internally if not logged in)
    role = require_login()

    # Sidebar controls + announcements (post-login)
    uploaded_files, enabled_files, search, min_delivery, max_cancel = sidebar_controls(role)
    sidebar_announcements(role)

    # Build master/filtered
    result = build_master_from_uploads(enabled_files, search, min_delivery, max_cancel)
    master_all, f = _split_master_and_filtered(result)

    # Route by role
    if role == "الإدارة":
        try:
            page_admin(master_all, f)
        except TypeError:
            page_admin(f)

    elif role == "التشغيل":
        try:
            page_ops(master_all, f)
        except TypeError:
            page_ops(f)

    elif role == "الموارد البشرية":
        page_hr()

    elif role == "الإشراف":
        try:
            page_supervision(master_all, f)
        except TypeError:
            page_supervision(f)

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
