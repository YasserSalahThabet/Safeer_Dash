import io
import re
from typing import Dict, Optional, List

import numpy as np
import pandas as pd
import streamlit as st

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="مسير الرواتب",
    page_icon="💼",
    layout="wide"
)

# --------------------------------------------------
# STYLE
# --------------------------------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
.title {
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
}
.subtitle {
    color: #666;
    margin-bottom: 1rem;
}
.card {
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.03);
    margin-bottom: 1rem;
}
.small-label {
    font-size: 0.9rem;
    color: #888;
}
.big-number {
    font-size: 1.4rem;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">💼 مسير الرواتب</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">واجهة نظيفة لإدارة الرواتب، تعديل البيانات، وعرض تفاصيل كل موظف.</div>', unsafe_allow_html=True)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def normalize_text(val) -> str:
    if val is None:
        return ""
    s = str(val).strip().translate(ARABIC_DIGITS)
    s = re.sub(r"\s+", " ", s)
    return s

def safe_num_series(series: pd.Series) -> pd.Series:
    def convert(x):
        if pd.isna(x):
            return np.nan
        s = normalize_text(x).replace(",", "")
        try:
            return float(s)
        except:
            return np.nan
    return series.apply(convert)

def safe_num_value(x):
    if pd.isna(x):
        return 0.0
    s = normalize_text(x).replace(",", "")
    try:
        return float(s)
    except:
        return 0.0

def guess_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = list(df.columns)
    normalized_cols = [normalize_text(c) for c in cols]

    for cand in candidates:
        cand_n = normalize_text(cand)
        for c, cn in zip(cols, normalized_cols):
            if cn == cand_n:
                return c

    for cand in candidates:
        cand_n = normalize_text(cand)
        for c, cn in zip(cols, normalized_cols):
            if cand_n in cn:
                return c
    return None

def ensure_numeric_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    df = df.copy()
    for c in columns:
        if c in df.columns:
            df[c] = safe_num_series(df[c])
    return df

def load_excel(uploaded_file) -> Dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(uploaded_file)
    sheets = {}
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        df.columns = [normalize_text(c) for c in df.columns]
        sheets[sheet] = df
    return sheets

def apply_global_adjustments(
    df: pd.DataFrame,
    bonus_col: Optional[str],
    deduction_col: Optional[str],
    global_bonus: float,
    global_deduction: float
) -> pd.DataFrame:
    df = df.copy()

    if global_bonus != 0:
        col = bonus_col if bonus_col else "بونس عام"
        if col not in df.columns:
            df[col] = 0.0
        df[col] = safe_num_series(df[col]).fillna(0) + float(global_bonus)

    if global_deduction != 0:
        col = deduction_col if deduction_col else "خصم عام"
        if col not in df.columns:
            df[col] = 0.0
        df[col] = safe_num_series(df[col]).fillna(0) + float(global_deduction)

    return df

def apply_shortage_rule(
    df: pd.DataFrame,
    orders_col: str,
    base_col: str,
    threshold: float,
    multiplier: float,
    diff_col: str = "فارق الطلبات",
    shortage_deduction_col: str = "خصم فارق الطلبات"
) -> pd.DataFrame:
    """
    If orders < threshold:
        shortage = threshold - orders
        deduction = shortage * multiplier
        new_base = original_base - deduction
    """
    df = df.copy()

    if orders_col not in df.columns or base_col not in df.columns:
        return df

    orders = safe_num_series(df[orders_col]).fillna(0)
    base = safe_num_series(df[base_col]).fillna(0)

    shortage = np.where(orders < threshold, threshold - orders, 0)
    shortage_deduction = shortage * multiplier
    new_base = base - shortage_deduction

    df[diff_col] = shortage
    df[shortage_deduction_col] = shortage_deduction
    df[base_col] = new_base

    return df

def recompute_payroll_exact(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    total = base + extra - deductions
    net = total
    """
    df = df.copy()

    base_col = mapping.get("base")
    extra_col = mapping.get("extra")
    total_col = mapping.get("total")
    net_col = mapping.get("net")

    deduction_keys = [
        "advance",
        "keeta",
        "late",
        "fuel",
        "supervisor",
        "general_deduction",
    ]

    if not base_col or base_col not in df.columns:
        return df

    base = safe_num_series(df[base_col]).fillna(0)
    extra = 0

    if extra_col and extra_col in df.columns:
        extra = safe_num_series(df[extra_col]).fillna(0)

    total_deductions = 0
    for key in deduction_keys:
        col = mapping.get(key)
        if col and col in df.columns:
            total_deductions = total_deductions + safe_num_series(df[col]).fillna(0)

    total_value = base + extra - total_deductions

    if total_col:
        if total_col not in df.columns:
            df[total_col] = 0.0
        df[total_col] = total_value

    if net_col:
        if net_col not in df.columns:
            df[net_col] = 0.0
        df[net_col] = total_value

    return df

def to_excel_bytes(sheets_dict: Dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, df in sheets_dict.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()

def format_money(x):
    try:
        return f"{float(x):,.2f}"
    except:
        return str(x)

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
if "sheets" not in st.session_state:
    st.session_state.sheets = {}
if "original_sheets" not in st.session_state:
    st.session_state.original_sheets = {}
if "loaded_file_name" not in st.session_state:
    st.session_state.loaded_file_name = None

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.header("📂 الملف")

    uploaded_file = st.file_uploader("ارفع ملف Excel", type=["xlsx"])

    st.markdown("---")
    st.subheader("⚙️ Payroll Rules / Requirements")

    apply_rule = st.toggle("تفعيل قاعدة فارق الطلبات", value=True)
    order_threshold = st.number_input(
        "حد الطلبات المطلوب",
        min_value=0.0,
        value=450.0,
        step=10.0
    )
    shortage_multiplier = st.number_input(
        "قيمة الضرب عند النقص",
        min_value=0.0,
        value=9.0,
        step=1.0
    )

    st.caption("لو كان عدد الطلبات أقل من الحد المطلوب، سيتم حساب فارق الطلبات × قيمة الضرب وخصمه من الراتب الأساسي.")

    st.markdown("---")
    st.subheader("➕➖ Global Adjustments")

    global_bonus = st.number_input(
        "Bonus for all employees",
        min_value=0.0,
        value=0.0,
        step=50.0
    )

    global_deduction = st.number_input(
        "Deduction for all employees",
        min_value=0.0,
        value=0.0,
        step=50.0
    )

    st.caption("يمكنك إضافة بونس أو خصم جماعي لكل الموظفين.")

# --------------------------------------------------
# LOAD FILE
# --------------------------------------------------
if uploaded_file is not None:
    if st.session_state.loaded_file_name != uploaded_file.name:
        sheets = load_excel(uploaded_file)
        st.session_state.original_sheets = {k: v.copy() for k, v in sheets.items()}
        st.session_state.sheets = {k: v.copy() for k, v in sheets.items()}
        st.session_state.loaded_file_name = uploaded_file.name

if not st.session_state.sheets:
    st.info("ارفع ملف Excel من القائمة الجانبية للبدء.")
    st.stop()

# --------------------------------------------------
# MAIN
# --------------------------------------------------
sheet_names = list(st.session_state.sheets.keys())
selected_sheet = st.selectbox("اختر الشيت", sheet_names)

df = st.session_state.sheets[selected_sheet].copy()

top_a, top_b = st.columns([3, 1])

with top_a:
    st.markdown("### بيانات الشيت")

with top_b:
    if st.button("إعادة ضبط الشيت الحالي"):
        st.session_state.sheets[selected_sheet] = st.session_state.original_sheets[selected_sheet].copy()
        st.rerun()

# --------------------------------------------------
# COLUMN MAPPING
# --------------------------------------------------
with st.expander("🔧 ربط الأعمدة", expanded=False):
    cols = [""] + list(df.columns)

    guessed_name = guess_column(df, ["اسم السائق", "اسم الموظف", "الاسم", "اسم"])
    guessed_orders = guess_column(df, ["عدد الطلبات", "عدد طلبات", "الطلبات"])
    guessed_base = guess_column(df, ["الراتب الأساسي", "الراتب الاساسي", "راتب أساسي", "راتب اساسي"])
    guessed_extra = guess_column(df, ["اضافي", "إضافي", "بونس", "مكافأة"])
    guessed_advance = guess_column(df, ["سلفيات", "سلفية", "سلفة"])
    guessed_keeta = guess_column(df, ["خصم كيتا"])
    guessed_late = guess_column(df, ["تأخير"])
    guessed_fuel = guess_column(df, ["بنزين"])
    guessed_supervisor = guess_column(df, ["محاضر مشرف"])
    guessed_total = guess_column(df, ["اجمالي الراتب المستحق", "إجمالي الراتب المستحق", "الاجمالي"])
    guessed_net = guess_column(df, ["الصافي", "صافي"])

    name_col = st.selectbox("عمود الاسم", cols, index=cols.index(guessed_name) if guessed_name in cols else 0)
    orders_col = st.selectbox("عمود عدد الطلبات", cols, index=cols.index(guessed_orders) if guessed_orders in cols else 0)
    base_col = st.selectbox("عمود الراتب الأساسي", cols, index=cols.index(guessed_base) if guessed_base in cols else 0)
    extra_col = st.selectbox("عمود الإضافي / البونس", cols, index=cols.index(guessed_extra) if guessed_extra in cols else 0)
    advance_col = st.selectbox("عمود سلفيات", cols, index=cols.index(guessed_advance) if guessed_advance in cols else 0)
    keeta_col = st.selectbox("عمود خصم كيتا", cols, index=cols.index(guessed_keeta) if guessed_keeta in cols else 0)
    late_col = st.selectbox("عمود تأخير", cols, index=cols.index(guessed_late) if guessed_late in cols else 0)
    fuel_col = st.selectbox("عمود بنزين", cols, index=cols.index(guessed_fuel) if guessed_fuel in cols else 0)
    supervisor_col = st.selectbox("عمود محاضر مشرف", cols, index=cols.index(guessed_supervisor) if guessed_supervisor in cols else 0)
    total_col = st.selectbox("عمود الإجمالي", cols, index=cols.index(guessed_total) if guessed_total in cols else 0)
    net_col = st.selectbox("عمود الصافي", cols, index=cols.index(guessed_net) if guessed_net in cols else 0)

mapping = {
    "name": name_col if name_col else None,
    "orders": orders_col if orders_col else None,
    "base": base_col if base_col else None,
    "extra": extra_col if extra_col else None,
    "advance": advance_col if advance_col else None,
    "keeta": keeta_col if keeta_col else None,
    "late": late_col if late_col else None,
    "fuel": fuel_col if fuel_col else None,
    "supervisor": supervisor_col if supervisor_col else None,
    "total": total_col if total_col else None,
    "net": net_col if net_col else None,
    "general_deduction": "خصم عام"
}

# --------------------------------------------------
# PREP DATA
# --------------------------------------------------
numeric_cols = [
    c for c in [
        orders_col, base_col, extra_col, advance_col,
        keeta_col, late_col, fuel_col, supervisor_col,
        total_col, net_col
    ] if c
]

df = ensure_numeric_columns(df, numeric_cols)

# Keep original base before rule, for transparency
if base_col and base_col in df.columns:
    if "الراتب الأساسي قبل قاعدة الطلبات" not in df.columns:
        df["الراتب الأساسي قبل قاعدة الطلبات"] = safe_num_series(df[base_col]).fillna(0)

# Global adjustments
df = apply_global_adjustments(
    df=df,
    bonus_col=extra_col if extra_col else "بونس عام",
    deduction_col="خصم عام",
    global_bonus=global_bonus,
    global_deduction=global_deduction
)

# Apply configurable shortage rule
if apply_rule and orders_col and base_col:
    df = apply_shortage_rule(
        df=df,
        orders_col=orders_col,
        base_col=base_col,
        threshold=order_threshold,
        multiplier=shortage_multiplier,
        diff_col="فارق الطلبات",
        shortage_deduction_col="خصم فارق الطلبات"
    )

# Recompute totals
df = recompute_payroll_exact(df, mapping)

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------
st.markdown("### 📊 الملخص")

s1, s2, s3, s4 = st.columns(4)

with s1:
    st.metric("عدد الموظفين", len(df))

with s2:
    if orders_col and orders_col in df.columns:
        st.metric("مجموع الطلبات", format_money(safe_num_series(df[orders_col]).fillna(0).sum()))
    else:
        st.metric("مجموع الطلبات", "—")

with s3:
    if total_col and total_col in df.columns:
        st.metric("مجموع الإجمالي", format_money(safe_num_series(df[total_col]).fillna(0).sum()))
    else:
        st.metric("مجموع الإجمالي", "—")

with s4:
    if net_col and net_col in df.columns:
        st.metric("مجموع الصافي", format_money(safe_num_series(df[net_col]).fillna(0).sum()))
    else:
        st.metric("مجموع الصافي", "—")

# --------------------------------------------------
# TABS
# --------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📋 الجدول", "👤 تفاصيل الموظف", "⬇️ التصدير"])

# --------------------------------------------------
# TAB 1 - TABLE
# --------------------------------------------------
with tab1:
    st.markdown("### ✍️ تعديل الجدول")

    st.info(
        f"القواعد الحالية: حد الطلبات = {format_money(order_threshold)} | "
        f"مضاعف النقص = {format_money(shortage_multiplier)} | "
        f"Bonus for all = {format_money(global_bonus)} | "
        f"Deduction for all = {format_money(global_deduction)}"
    )

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key=f"editor_{selected_sheet}"
    )

    st.session_state.sheets[selected_sheet] = edited_df.copy()

# --------------------------------------------------
# TAB 2 - DRIVER DETAILS
# --------------------------------------------------
with tab2:
    st.markdown("### 👤 تفاصيل الموظف")

    current_df = st.session_state.sheets[selected_sheet].copy()

    if name_col and name_col in current_df.columns:
        driver_names = current_df[name_col].fillna("").astype(str).tolist()
        selected_driver = st.selectbox("اختر موظف", driver_names)

        driver_row = current_df[current_df[name_col].astype(str) == str(selected_driver)]

        if not driver_row.empty:
            row = driver_row.iloc[0]

            a, b, c = st.columns(3)

            with a:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="small-label">الاسم</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="big-number">{row.get(name_col, "")}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with b:
                orders_val = row.get(orders_col, 0) if orders_col else 0
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="small-label">عدد الطلبات</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="big-number">{format_money(orders_val)}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with c:
                base_val = row.get(base_col, 0) if base_col else 0
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<div class="small-label">الراتب الأساسي</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="big-number">{format_money(base_val)}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            d1, d2, d3 = st.columns(3)

            with d1:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.write(f"**سلفيات:** {format_money(row.get(advance_col, 0) if advance_col else 0)}")
                st.write(f"**خصم كيتا:** {format_money(row.get(keeta_col, 0) if keeta_col else 0)}")
                st.write(f"**تأخير:** {format_money(row.get(late_col, 0) if late_col else 0)}")
                st.markdown('</div>', unsafe_allow_html=True)

            with d2:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.write(f"**بنزين:** {format_money(row.get(fuel_col, 0) if fuel_col else 0)}")
                st.write(f"**محاضر مشرف:** {format_money(row.get(supervisor_col, 0) if supervisor_col else 0)}")
                st.write(f"**إضافي / بونس:** {format_money(row.get(extra_col, 0) if extra_col else 0)}")
                st.markdown('</div>', unsafe_allow_html=True)

            with d3:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.write(f"**فارق الطلبات:** {format_money(row.get('فارق الطلبات', 0))}")
                st.write(f"**خصم فارق الطلبات:** {format_money(row.get('خصم فارق الطلبات', 0))}")
                st.write(f"**خصم عام:** {format_money(row.get('خصم عام', 0))}")
                st.markdown('</div>', unsafe_allow_html=True)

            e1, e2 = st.columns(2)

            with e1:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.write(f"**الإجمالي:** {format_money(row.get(total_col, 0) if total_col else 0)}")
                st.markdown('</div>', unsafe_allow_html=True)

            with e2:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.write(f"**الصافي:** {format_money(row.get(net_col, 0) if net_col else 0)}")
                st.markdown('</div>', unsafe_allow_html=True)

            with st.expander("عرض كل بيانات الموظف"):
                all_data = pd.DataFrame({
                    "الحقل": current_df.columns,
                    "القيمة": [row[col] for col in current_df.columns]
                })
                st.dataframe(all_data, use_container_width=True, hide_index=True)
    else:
        st.info("اختر عمود الاسم من قسم ربط الأعمدة لعرض تفاصيل الموظف.")

# --------------------------------------------------
# TAB 3 - EXPORT
# --------------------------------------------------
with tab3:
    st.markdown("### ⬇️ تنزيل الملف")

    excel_data = to_excel_bytes(st.session_state.sheets)

    st.download_button(
        label="تنزيل ملف الرواتب المعدل",
        data=excel_data,
        file_name="مسير_الرواتب_المعدل.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )