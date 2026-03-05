import streamlit as st
import pandas as pd
from io import BytesIO

ORDERS_TARGET = 450

def _read_xlsx(file_bytes: bytes) -> pd.DataFrame:
    bio = BytesIO(file_bytes)
    xls = pd.ExcelFile(bio)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(bio, sheet_name=sheet, header=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def _pick(cols, candidates):
    cols = [str(c).strip() for c in cols]
    for c in candidates:
        if c in cols:
            return c
    return None

def _fmt_money(x):
    try:
        if pd.isna(x): return ""
        return f"{float(x):,.2f}"
    except Exception:
        return str(x)

def page_payroll(enabled_files):
    st.subheader("🧾 مسير الرواتب")

    # This page uses its own payroll format (you said this is the only needed format)
    # We read the first enabled file that matches payroll signals, else ask user to enable one.
    if not enabled_files:
        st.info("فعّل ملف مسير الرواتب من (📄 الملفات المرفوعة) في الشريط الجانبي.")
        return

    # Try to find payroll file by columns
    payroll_df = None
    payroll_name = None

    for uf in enabled_files:
        df_try = _read_xlsx(uf.getvalue())
        cols = set(df_try.columns)
        if ("عدد الطلبات" in cols) or ("الرصيد" in cols) or ("الراتب الاساسي" in cols) or ("الراتب الأساسي" in cols):
            payroll_df = df_try
            payroll_name = uf.name
            break

    if payroll_df is None:
        st.warning("لم يتم العثور على ملف مسير رواتب بين الملفات المفعّلة. فعّل ملف المسير.")
        return

    st.caption(f"الملف الحالي: {payroll_name}")

    orders_col = _pick(payroll_df.columns, ["عدد الطلبات", "الطلبات", "طلبات"])
    base_col = _pick(payroll_df.columns, ["الراتب الاساسي", "الراتب الأساسي", "راتب اساسي"])
    name_col = _pick(payroll_df.columns, ["اسم السائق", "اسم الموظف", "الاسم", "Name"])
    id_col = _pick(payroll_df.columns, ["معرف السائق", "معرّف السائق", "Driver_ID", "driver_id", "id"])

    if orders_col is None:
        st.error("❌ لا يوجد عمود (عدد الطلبات) في ملف مسير الرواتب.")
        st.write(list(payroll_df.columns))
        return

    df = payroll_df.copy()
    df[orders_col] = pd.to_numeric(df[orders_col], errors="coerce").fillna(0)

    # Rule:
    # If orders < 450: ignore base salary and replace with (orders * 7)
    # Else: keep base salary (if exists), otherwise also use (orders * 7)
    df["الراتب_المستحق"] = df[orders_col] * 7

    if base_col is not None:
        df[base_col] = pd.to_numeric(df[base_col], errors="coerce")
        df["الراتب_المستحق"] = df.apply(
            lambda r: (r[orders_col] * 7) if r[orders_col] < ORDERS_TARGET else (r[base_col] if pd.notna(r[base_col]) else (r[orders_col] * 7)),
            axis=1
        )

    # Nice display columns (keep all existing, plus computed)
    display_cols = []
    for c in [id_col, name_col, orders_col]:
        if c and c in df.columns:
            display_cols.append(c)
    if base_col and base_col in df.columns:
        display_cols.append(base_col)
    display_cols += ["الراتب_المستحق"]

    st.dataframe(
        df[display_cols].style.format({"الراتب_المستحق": _fmt_money}),
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇️ تحميل مسير الرواتب (CSV)",
        data=df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="safeer_payroll.csv",
        mime="text/csv"
    )
