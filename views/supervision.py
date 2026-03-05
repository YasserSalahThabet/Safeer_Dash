import streamlit as st
import pandas as pd
from core.excel import style_attention_table


def page_supervision(f: pd.DataFrame | None):
    st.subheader("🧭 الإشراف")
    if f is None or len(f) == 0:
        st.info("ارفع ملف/ملفات الأداء للبدء.")
        return
    cols = ["ترتيب المتابعة", "معرّف السائق", "اسم السائق", "معدل توصيل", "معدل الغاء", "طلبات", "المهام المرفوضة"]
    st.dataframe(style_attention_table(f[cols].head(120)), use_container_width=True, hide_index=True)
