import streamlit as st
import pandas as pd
import plotly.express as px

from core.excel import style_attention_table


def _fmt_int(x):
    try:
        if pd.isna(x):
            return "—"
        return f"{int(round(float(x))):,}"
    except Exception:
        return str(x)


def _safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def _build_lookup_source(master_all: pd.DataFrame | None, f: pd.DataFrame | None) -> pd.DataFrame:
    """
    Driver lookup should use master_all so it never disappears after filters.
    """
    src = master_all if master_all is not None and len(master_all) else f
    if src is None or len(src) == 0:
        return pd.DataFrame()

    out = src.copy()
    out = out.dropna(subset=["معرّف السائق"]).copy()
    out["معرّف السائق"] = pd.to_numeric(out["معرّف السائق"], errors="coerce").astype("Int64")
    out["اسم السائق"] = out["اسم السائق"].astype(str).str.strip()
    out = out.drop_duplicates(subset=["معرّف السائق"])
    out["اختيار"] = out["اسم السائق"] + " — " + out["معرّف السائق"].astype(str)
    out = out.sort_values(["اسم السائق", "معرّف السائق"])
    return out


def _render_driver_lookup(master_all: pd.DataFrame | None, f: pd.DataFrame | None):
    st.subheader("🔎 بحث عن سائق")

    lookup_df = _build_lookup_source(master_all, f)
    if lookup_df.empty:
        st.info("لا توجد بيانات سائقين للعرض.")
        return

    options = lookup_df["اختيار"].tolist()
    selected = st.selectbox("اختر السائق", ["(اختر)"] + options, key="lookup_driver")

    if selected == "(اختر)":
        return

    did = int(selected.split("—")[-1].strip())
    row = lookup_df[lookup_df["معرّف السائق"].astype("Int64") == did].head(1)
    if row.empty:
        st.info("لم يتم العثور على بيانات السائق.")
        return

    d = row.iloc[0]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("معدل توصيل %", f"{float(d['معدل توصيل']):.2%}" if pd.notna(d.get("معدل توصيل")) else "—")
    c2.metric("طلبات", _fmt_int(d.get("طلبات")))
    c3.metric("معدل الغاء %", f"{float(d['معدل الغاء']):.2%}" if pd.notna(d.get("معدل الغاء")) else "—")
    c4.metric("المهام المرفوضة", _fmt_int(d.get("المهام المرفوضة")))

    fr = d.get("FR", None)
    vda = d.get("VDA", None)
    c5.metric("FR", _fmt_int(fr) if fr is not None else "—")
    c6.metric("VDA", _fmt_int(vda) if vda is not None else "—")


def _render_fr_vda_insights(master_all: pd.DataFrame | None, f: pd.DataFrame | None):
    st.subheader("📊 Insight — FR / VDA")

    src = master_all if master_all is not None and len(master_all) else f
    if src is None or len(src) == 0:
        st.info("لا توجد بيانات FR / VDA حالياً.")
        return

    df = src.copy()

    if "FR" not in df.columns and "VDA" not in df.columns:
        st.info("لم يتم العثور على أعمدة FR أو VDA.")
        return

    if "FR" in df.columns:
        df["FR"] = _safe_numeric(df["FR"])
    if "VDA" in df.columns:
        df["VDA"] = _safe_numeric(df["VDA"])

    k1, k2, k3, k4 = st.columns(4)

    if "FR" in df.columns:
        k1.metric("عدد سجلات FR", f"{int(df['FR'].notna().sum()):,}")
        k2.metric("متوسط FR", f"{float(df['FR'].fillna(0).mean()):.2f}")
    else:
        k1.metric("عدد سجلات FR", "0")
        k2.metric("متوسط FR", "—")

    if "VDA" in df.columns:
        k3.metric("عدد سجلات VDA", f"{int(df['VDA'].notna().sum()):,}")
        k4.metric("متوسط VDA", f"{float(df['VDA'].fillna(0).mean()):.2f}")
    else:
        k3.metric("عدد سجلات VDA", "0")
        k4.metric("متوسط VDA", "—")

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        if "FR" in df.columns:
            fr_chart = df[["اسم السائق", "FR"]].copy()
            fr_chart = fr_chart.dropna(subset=["FR"]).sort_values("FR", ascending=False).head(20)
            if len(fr_chart):
                st.markdown("### أعلى 20 سائق حسب FR")
                fig_fr = px.bar(fr_chart, x="اسم السائق", y="FR")
                st.plotly_chart(fig_fr, use_container_width=True)
            else:
                st.info("لا توجد بيانات FR للعرض.")

    with c2:
        if "VDA" in df.columns:
            vda_chart = df[["اسم السائق", "VDA"]].copy()
            vda_chart = vda_chart.dropna(subset=["VDA"]).sort_values("VDA", ascending=False).head(20)
            if len(vda_chart):
                st.markdown("### أعلى 20 سائق حسب VDA")
                fig_vda = px.bar(vda_chart, x="اسم السائق", y="VDA")
                st.plotly_chart(fig_vda, use_container_width=True)
            else:
                st.info("لا توجد بيانات VDA للعرض.")

    st.divider()

    insight_cols = ["معرّف السائق", "اسم السائق"]
    if "FR" in df.columns:
        insight_cols.append("FR")
    if "VDA" in df.columns:
        insight_cols.append("VDA")

    st.markdown("### جدول FR / VDA")
    st.dataframe(df[insight_cols], use_container_width=True, hide_index=True)


def page_ops(master_all: pd.DataFrame | None, f: pd.DataFrame | None):
    st.subheader("🚚 التشغيل")
    if f is None or len(f) == 0:
        st.info("ارفع ملف/ملفات الأداء للبدء.")
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("عدد السائقين", f"{int(f['معرّف السائق'].nunique()):,}")
    k2.metric("متوسط معدل التوصيل", f"{float(f['معدل توصيل'].mean()):.2%}")
    k3.metric("متوسط معدل الإلغاء", f"{float(f['معدل الغاء'].mean()):.2%}")
    k4.metric("عدد الطلبات", f"{int(pd.to_numeric(f['طلبات'], errors='coerce').fillna(0).sum()):,}")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "الأولوية",
        "بحث عن سائق",
        "FR / VDA Insight",
        "الجدول النهائي"
    ])

    with tab1:
        st.subheader("🚨 سائقون يحتاجون متابعة (الأولوية أولاً)")
        attention_cols = [
            "ترتيب المتابعة", "معرّف السائق", "اسم السائق",
            "معدل توصيل", "معدل الغاء", "طلبات", "المهام المرفوضة"
        ]
        st.dataframe(
            style_attention_table(f[attention_cols].head(80)),
            use_container_width=True,
            hide_index=True
        )

    with tab2:
        _render_driver_lookup(master_all, f)

    with tab3:
        _render_fr_vda_insights(master_all, f)

    with tab4:
        st.subheader("📋 الجدول النهائي (كامل البيانات)")
        base_cols = [
            "معرّف السائق", "اسم السائق", "معدل توصيل",
            "معدل الغاء", "طلبات", "المهام المرفوضة"
        ]
        extra = []
        if "FR" in f.columns:
            extra.append("FR")
        if "VDA" in f.columns:
            extra.append("VDA")

        cols = base_cols + extra

        st.dataframe(
            f[cols].style.format({
                "معدل توصيل": "{:.2%}",
                "معدل الغاء": "{:.2%}"
            }),
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "⬇️ تحميل النتائج CSV",
            data=f.to_csv(index=False, encoding="utf-8-sig"),
            file_name="safeer_master_filtered.csv",
            mime="text/csv",
        )