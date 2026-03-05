import streamlit as st
import pandas as pd

from core.excel import style_attention_table


def _fmt_int(x):
    try:
        if pd.isna(x): return "—"
        return f"{int(round(float(x))):,}"
    except Exception:
        return str(x)


def page_ops(f: pd.DataFrame | None):
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
    st.subheader("🚨 سائقون يحتاجون متابعة (الأولوية أولاً)")
    attention_cols = ["ترتيب المتابعة", "معرّف السائق", "اسم السائق", "معدل توصيل", "معدل الغاء", "طلبات", "المهام المرفوضة"]
    st.dataframe(style_attention_table(f[attention_cols].head(80)), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🔎 بحث عن سائق")

    # Use "Name — ID" to avoid duplicate names
    f2 = f.copy()
    f2["اختيار"] = f2["اسم السائق"].astype(str).str.strip() + " — " + f2["معرّف السائق"].astype(str)
    options = f2[["اختيار", "معرّف السائق"]].dropna().drop_duplicates("اختيار").sort_values("اختيار")["اختيار"].tolist()

    selected = st.selectbox("اختر السائق", ["(اختر)"] + options, key="lookup_driver")
    if selected != "(اختر)":
        did = int(selected.split("—")[-1].strip())
        row = f2[f2["معرّف السائق"].astype("Int64") == did].head(1)
        if len(row):
            d = row.iloc[0]
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("معدل توصيل %", f"{float(d['معدل توصيل']):.2%}")
            c2.metric("طلبات", _fmt_int(d["طلبات"]))
            c3.metric("معدل الغاء %", f"{float(d['معدل الغاء']):.2%}")
            c4.metric("المهام المرفوضة", _fmt_int(d["المهام المرفوضة"]))
            fr = d.get("FR", None)
            vda = d.get("VDA", None)
            c5.metric("FR", _fmt_int(fr) if fr is not None else "—")
            c6.metric("VDA", _fmt_int(vda) if vda is not None else "—")

    st.divider()
    st.subheader("📋 الجدول النهائي (كامل البيانات)")
    base_cols = ["معرّف السائق", "اسم السائق", "معدل توصيل", "معدل الغاء", "طلبات", "المهام المرفوضة"]
    extra = []
    if "FR" in f.columns: extra.append("FR")
    if "VDA" in f.columns: extra.append("VDA")
    cols = base_cols + extra

    st.dataframe(
        f[cols].style.format({"معدل توصيل": "{:.2%}", "معدل الغاء": "{:.2%}"}),
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇️ تحميل النتائج CSV",
        data=f.to_csv(index=False, encoding="utf-8-sig"),
        file_name="safeer_master_filtered.csv",
        mime="text/csv",
    )
