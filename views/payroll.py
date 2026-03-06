import streamlit as st
import pandas as pd
from io import BytesIO

ORDERS_TARGET = 450
SHORTAGE_RATE = 9

def _norm(s):
    return str(s).strip().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا") if s is not None else ""

def _read_matching_xlsx(file_bytes: bytes) -> tuple[pd.DataFrame, str]:
    bio = BytesIO(file_bytes)
    xls = pd.ExcelFile(bio)

    payroll_signals = {"عدد الطلبات", "الرصيد", "الراتب الاساسي", "الراتب الأساسي"}

    for sheet in xls.sheet_names:
        df = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet, header=0)
        df.columns = [str(c).strip() for c in df.columns]
        cols = set(df.columns)
        if any(sig in cols for sig in payroll_signals):
            return df, sheet

    # fallback to first sheet
    first_sheet = xls.sheet_names[0]
    df = pd.read_excel(BytesIO(file_bytes), sheet_name=first_sheet, header=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df, first_sheet

def _pick(cols, candidates):
    raw_cols = [str(c).strip() for c in cols]
    norm_map = {_norm(c): c for c in raw_cols}

    for cand in candidates:
        if cand in raw_cols:
            return cand

    for cand in candidates:
        nc = _norm(cand)
        if nc in norm_map:
            return norm_map[nc]

    for cand in candidates:
        nc = _norm(cand)
        for col in raw_cols:
            if nc in _norm(col):
                return col

    return None

def _fmt_money(x):
    try:
        if pd.isna(x):
            return ""
        return f"{float(x):,.2f}"
    except Exception:
        return str(x)

def _to_num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)

def _xlsx_download(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Payroll")
    output.seek(0)
    return output.getvalue()

def page_payroll(enabled_files):
    st.subheader("🧾 مسير الرواتب")

    if not enabled_files:
        st.info("فعّل ملف مسير الرواتب من (📄 الملفات المرفوعة) في الشريط الجانبي.")
        return

    payroll_df = None
    payroll_name = None
    payroll_sheet = None

    for uf in enabled_files:
        try:
            df_try, sheet_try = _read_matching_xlsx(uf.getvalue())
            cols = set(df_try.columns)
            if ("عدد الطلبات" in cols) or ("الرصيد" in cols) or ("الراتب الاساسي" in cols) or ("الراتب الأساسي" in cols):
                payroll_df = df_try
                payroll_name = uf.name
                payroll_sheet = sheet_try
                break
        except Exception:
            continue

    if payroll_df is None:
        st.warning("لم يتم العثور على ملف مسير رواتب بين الملفات المفعّلة. فعّل ملف المسير.")
        return

    st.caption(f"الملف الحالي: {payroll_name} | الشيت: {payroll_sheet}")

    orders_col = _pick(payroll_df.columns, ["عدد الطلبات", "الطلبات", "طلبات"])
    base_col = _pick(payroll_df.columns, ["الراتب الاساسي", "الراتب الأساسي", "راتب اساسي"])
    name_col = _pick(payroll_df.columns, ["اسم السائق", "اسم الموظف", "الاسم", "Name"])
    id_col = _pick(payroll_df.columns, ["معرف السائق", "معرّف السائق", "Driver_ID", "driver_id", "id"])

    advance_col = _pick(payroll_df.columns, ["سلفيات", "سلفية", "سلفة"])
    keeta_col = _pick(payroll_df.columns, ["خصم كيتا"])
    late_col = _pick(payroll_df.columns, ["تأخير"])
    fuel_col = _pick(payroll_df.columns, ["بنزين"])
    supervisor_col = _pick(payroll_df.columns, ["محاضر مشرف"])
    extra_col = _pick(payroll_df.columns, ["اضافي", "إضافي"])

    if orders_col is None:
        st.error("❌ لا يوجد عمود (عدد الطلبات) في ملف مسير الرواتب.")
        st.write(list(payroll_df.columns))
        return

    if base_col is None:
        st.error("❌ لا يوجد عمود (الراتب الأساسي) في ملف مسير الرواتب.")
        st.write(list(payroll_df.columns))
        return

    df = payroll_df.copy()

    df[orders_col] = _to_num(df[orders_col])
    df[base_col] = _to_num(df[base_col])

    for col in [advance_col, keeta_col, late_col, fuel_col, supervisor_col, extra_col]:
        if col and col in df.columns:
            df[col] = _to_num(df[col])

    df["نقص_الطلبات"] = (ORDERS_TARGET - df[orders_col]).clip(lower=0)
    df["خصم_نقص_الطلبات"] = df["نقص_الطلبات"] * SHORTAGE_RATE
    df["الراتب_بعد_تعديل_الطلبات"] = (df[base_col] - df["خصم_نقص_الطلبات"]).clip(lower=0)

    # Optional final salary including extras/deductions
    df["الراتب_النهائي"] = df["الراتب_بعد_تعديل_الطلبات"]

    if extra_col:
        df["الراتب_النهائي"] += df[extra_col]
    if advance_col:
        df["الراتب_النهائي"] -= df[advance_col]
    if keeta_col:
        df["الراتب_النهائي"] -= df[keeta_col]
    if late_col:
        df["الراتب_النهائي"] -= df[late_col]
    if fuel_col:
        df["الراتب_النهائي"] -= df[fuel_col]
    if supervisor_col:
        df["الراتب_النهائي"] -= df[supervisor_col]

    st.markdown("### ملخص الرواتب")

    display_cols = []
    for c in [id_col, name_col, orders_col, base_col]:
        if c and c in df.columns:
            display_cols.append(c)

    display_cols += ["نقص_الطلبات", "خصم_نقص_الطلبات", "الراتب_بعد_تعديل_الطلبات", "الراتب_النهائي"]

    st.dataframe(
        df[display_cols].style.format({
            "خصم_نقص_الطلبات": _fmt_money,
            "الراتب_بعد_تعديل_الطلبات": _fmt_money,
            "الراتب_النهائي": _fmt_money,
        }),
        use_container_width=True,
        hide_index=True
    )

    if name_col and name_col in df.columns:
        st.markdown("### 👤 تفاصيل السائق")
        driver_options = df[name_col].fillna("").astype(str).tolist()
        selected_driver = st.selectbox("اختر السائق", driver_options)

        driver_row = df[df[name_col].astype(str) == str(selected_driver)]
        if not driver_row.empty:
            r = driver_row.iloc[0]

            c1, c2 = st.columns(2)

            with c1:
                st.write(f"**الاسم:** {r.get(name_col, '')}")
                if id_col:
                    st.write(f"**المعرف:** {r.get(id_col, '')}")
                st.write(f"**عدد الطلبات:** {_fmt_money(r.get(orders_col, 0))}")
                st.write(f"**الراتب الأساسي:** {_fmt_money(r.get(base_col, 0))}")
                st.write(f"**نقص الطلبات:** {_fmt_money(r.get('نقص_الطلبات', 0))}")
                st.write(f"**خصم نقص الطلبات:** {_fmt_money(r.get('خصم_نقص_الطلبات', 0))}")

            with c2:
                if advance_col:
                    st.write(f"**سلفيات:** {_fmt_money(r.get(advance_col, 0))}")
                if keeta_col:
                    st.write(f"**خصم كيتا:** {_fmt_money(r.get(keeta_col, 0))}")
                if late_col:
                    st.write(f"**تأخير:** {_fmt_money(r.get(late_col, 0))}")
                if fuel_col:
                    st.write(f"**بنزين:** {_fmt_money(r.get(fuel_col, 0))}")
                if supervisor_col:
                    st.write(f"**محاضر مشرف:** {_fmt_money(r.get(supervisor_col, 0))}")
                if extra_col:
                    st.write(f"**اضافي:** {_fmt_money(r.get(extra_col, 0))}")
                st.write(f"**الراتب النهائي:** {_fmt_money(r.get('الراتب_النهائي', 0))}")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "⬇️ تحميل مسير الرواتب (CSV)",
            data=df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="safeer_payroll.csv",
            mime="text/csv"
        )

    with col2:
        st.download_button(
            "⬇️ تحميل مسير الرواتب (Excel)",
            data=_xlsx_download(df),
            file_name="safeer_payroll.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )