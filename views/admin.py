import streamlit as st
import pandas as pd
import plotly.express as px
from core.excel import style_attention_table


def page_admin(f: pd.DataFrame | None):
    st.subheader("📊 الإدارة — نظرة (يومي / شهري)")
    if f is None or len(f) == 0:
        st.info("قم بتحميل ملف/ملفات الأداء لعرض مؤشرات الإدارة.")
        return

    total_drivers = int(f["معرّف السائق"].nunique())
    total_orders = int(pd.to_numeric(f["طلبات"], errors="coerce").fillna(0).sum())
    avg_delivery = float(f["معدل توصيل"].mean()) if len(f) else 0
    avg_cancel = float(f["معدل الغاء"].mean()) if len(f) else 0

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("إجمالي السائقين", f"{total_drivers:,}")
    a2.metric("إجمالي الطلبات المكتملة", f"{total_orders:,}")
    a3.metric("متوسط معدل التوصيل", f"{avg_delivery:.2%}")
    a4.metric("متوسط معدل الإلغاء", f"{avg_cancel:.2%}")

    st.divider()
    st.markdown("### 🚨 الأولوية")
    cols = ["ترتيب المتابعة", "معرّف السائق", "اسم السائق", "معدل توصيل", "معدل الغاء", "طلبات", "المهام المرفوضة"]
    st.dataframe(style_attention_table(f[cols].head(30)), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### 📈 توزيع معدل الإلغاء")
    fig = px.histogram(f, x="معدل الغاء", nbins=30)
    st.plotly_chart(fig, use_container_width=True)
