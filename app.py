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


def _is_master_df(df) -> bool:
    """Unfiltered master usually has driver id + name columns at minimum."""
    if df is None:
        return False
    try:
        cols = set(df.columns)
        return ("معرّف السائق" in cols) and ("اسم السائق" in cols)
    except Exception:
        return False


def _is_filtered_df(df) -> bool:
    """Filtered/prioritized df often has 'ترتيب المتابعة' and/or 'أولوية'."""
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
      - (None, None)
    This detects and returns: (master_all, f)
    """
    master_all, f = None, None

    if not isinstance(result, (tuple, list)) or len(result) != 2:
        return None, None

    a, b = result[0], result[1]

    # If one looks like filtered and the other looks like master, assign accordingly
    if _is_filtered_df(a) and _is_master_df(b):
        f, master_all = a, b
    elif _is_master_df(a) and _is_filtered_df(b):
        master_all, f = a, b
    else:
        # If both look like master (or both unknown), prefer:
        # - master_all = one with more rows
        # - f = other (or same)
        try:
            if _is_master_df(a) and _is_master_df(b):
                # pick larger as master
                if len(a) >= len(b):
                    master_all, f = a, b
                else:
                    master_all, f = b, a
            else:
                # fallback: assume old order (f, master)
                f, master_all = a, b
        except Exception:
            f, master_all = a, b

    return master_all, f


def main():
    # Page setup
    init_page()
    apply_css()
    init_db()

    # Login
    role = require_login()

    # Sidebar controls (uploader + checklist + filters)
    uploaded_files, enabled_files, search, min_delivery, max_cancel = sidebar_controls(role)

    # Announcements: everyone sees; only الإدارة + التشغيل manage (handled inside core.ui)
    sidebar_announcements(role)

    # Header (images + title)
    render_header()

    # Build data
    # IMPORTANT: we want BOTH master_all (unfiltered) and f (filtered)
    result = build_master_from_uploads(enabled_files, search, min_delivery, max_cancel)
    master_all, f = _split_master_and_filtered(result)

    # Route by role
    if role == "الإدارة":
        # Admin pages usually need the filtered priority table + sometimes overall metrics
        # If your admin page only accepts one df, we pass f.
        # If it accepts two, update the view file (not here).
        page_admin(master_all, f) if page_admin.__code__.co_argcount >= 2 else page_admin(f)

    elif role == "التشغيل":
        # Ops NEEDS master_all for driver lookup + f for priority tables
        page_ops(master_all, f) if page_ops.__code__.co_argcount >= 2 else page_ops(f)

    elif role == "الموارد البشرية":
        page_hr()

    elif role == "الإشراف":
        # Supervision also benefits from lookup (master_all) + priority (f)
        page_supervision(master_all, f) if page_supervision.__code__.co_argcount >= 2 else page_supervision(f)

    elif role == "السيارات / الحركة":
        page_fleet()

    elif role == "الحسابات":
        page_accounts()

    elif role == "مسير الرواتب":
        # Payroll uses ONLY the enabled payroll file(s)
        page_payroll(enabled_files)

    else:
        st.info("الدور غير معروف.")


if __name__ == "__main__":
    main()
