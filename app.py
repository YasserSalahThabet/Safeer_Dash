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


def main():
    init_page()
    apply_css()
    init_db()

    role = require_login()

    # Sidebar controls (uploader + file checklist + filters)
    uploaded_files, enabled_files, search, min_delivery, max_cancel = sidebar_controls(role)

    # Announcements (everyone sees; only الإدارة + التشغيل manage)
    sidebar_announcements(role)

    # Header
    render_header()

    # Build performance master (only for pages that need it)
    f, master = build_master_from_uploads(enabled_files, search, min_delivery, max_cancel)

    # Route by role (NO extra menu)
    if role == "الإدارة":
        page_admin(f)
    elif role == "التشغيل":
        page_ops(f)
    elif role == "الموارد البشرية":
        page_hr()
    elif role == "الإشراف":
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
