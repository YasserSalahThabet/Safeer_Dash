import streamlit as st
from core.db import get_hr_registry


def page_hr():
    st.subheader("👥 الموارد البشرية — سجل السائقين (دائم)")
    registry = get_hr_registry()
    st.dataframe(registry, use_container_width=True, hide_index=True)
