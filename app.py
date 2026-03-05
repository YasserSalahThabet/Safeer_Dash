import streamlit as st

from core.config import init_page, apply_css
from core.db import init_db
from core.auth import require_login
from core.ui import render_header, sidebar_controls, sidebar_announcements
from core.excel import build_master_from_uploads

from views.admin import page_admin
from views.ops import page_ops
from views.hr import page_hr
from views.supervision import page_supervision
from views.fleet import page_fleet
from views.accounts import page_accounts
from views.payroll import page_payroll


def _top_safe_css():
    """
    Fix: page appears cropped at the top / header overlaps.
    Keep it minimal and safe for Streamlit 1.54+.
    """
    st.markdown(
        """
        <style>
        /* Give the whole app breathing room from the very top */
        .block-container { padding-top: 1.25rem !important; }

        /* Sidebar top spacing so logo isn't stuck/cropped */
        section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }

        /* Prevent images from being visually cropped in some layouts */
        img { object-fit: contain; }

        /* Hide Streamlit default menu/footer (optional, but helps clean layout) */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True
    )


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
    build_master_from_uploads may return:
      - (f, master)
      - (master, f)
    We normalize to: (master_all, f)
    """
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        return None, None

    a, b = result[0], result[1]

    # (filtered, master)
    if _is_filtered_df(a) and _is_master_df(b):
        return b, a

    # (master, filtered)
    if _is_master_df(a) and _is_filtered_df(b):
        return a, b

    # both master-ish -> pick larger as master
    try:
        if _is_master_df(a) and _is_master_df(b):
            if len(a) >= len(b):
                return a, b
            return b, a
    except Exception:
        pass

    # fallback assume old order (f, master)
    return b, a


def main():
    # 1) Config first
    init_page()

    # 2) Fix top cropping BEFORE anything else renders
    _top_safe_css()

    # 3) Your app CSS
    apply_css()

    # 4) DB ready
    init_db()

    # 5) Login (this should render the sidebar logo inside require_login)
    role = require_login()

    # 6) Sidebar controls (uploader + checklist + filters)
    uploaded_files, enabled_files, search, min_delivery, max_cancel = sidebar_controls(role)

    # 7) Announcements (everyone sees; only الإدارة + التشغيل manage)
    sidebar_announcements(role)

    # 8) Header images/title (this is where your left/right images should appear)
    render_header()

    # 9) Build data
    result = build_master_from_uploads(enabled_files, search, min_delivery, max_cancel)
    master_all, f = _split_master_and_filtered(result)

    # 10) Route by role (NO extra menu)
    if role == "الإدارة":
        # prefer signature (master_all, f) if supported
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
