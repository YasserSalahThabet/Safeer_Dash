import streamlit as st
from core.config import LOGO_IMG

DEFAULT_PASSWORD = "12345"

ROLES = {
    "الإدارة": "admin_password",
    "التشغيل": "ops_password",
    "الموارد البشرية": "hr_password",
    "الإشراف": "sup_password",
    "السيارات / الحركة": "fleet_password",
    "الحسابات": "accounts_password",
    "مسير الرواتب": "payroll_password",
}


def get_secret(key: str, default: str = DEFAULT_PASSWORD) -> str:
    """
    Reads password from st.secrets["auth"][key].
    If secrets are missing (e.g., local run without secrets), default to 12345.
    """
    try:
        auth = st.secrets.get("auth", {})
        val = auth.get(key, None)
        if val is None or str(val).strip() == "":
            return default
        return str(val)
    except Exception:
        return default


def require_login() -> str:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.role = None

    with st.sidebar:
        if LOGO_IMG.exists():
            st.image(str(LOGO_IMG), use_container_width=True)

        st.markdown("## تسجيل الدخول")
        role = st.selectbox("الدور", list(ROLES.keys()))
        pwd = st.text_input("كلمة المرور", type="password")
        col1, col2 = st.columns(2)
        login = col1.button("دخول")
        logout = col2.button("خروج")

        if logout:
            st.session_state.logged_in = False
            st.session_state.role = None
            st.rerun()

        if login:
            expected = get_secret(ROLES[role])
            if str(pwd).strip() == str(expected).strip():
                st.session_state.logged_in = True
                st.session_state.role = role
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة.")

    if not st.session_state.logged_in:
        st.info("الرجاء تسجيل الدخول من الشريط الجانبي.")
        st.stop()

    return st.session_state.role
