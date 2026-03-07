import io
import re
from pathlib import Path
from typing import Dict, Optional, List

import numpy as np
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def pick_asset(*names: str) -> Path:
    for n in names:
        p = ASSETS / n
        if p.exists():
            return p
    return ASSETS / names[0]


LOGO_IMG = pick_asset("logo.png", "logo.jpg")
HERO_IMG = pick_asset("hero.png", "left.jpg", "left.png")


def page_payroll(enabled_files=None):
    st.markdown("""
    <style>
    .block-container {
        padding-top: 2.1rem !important;
        padding-bottom: 2rem;
    }
    .payroll-title-wrap {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 0.3rem;
    }
    .payroll-logo {
        width: 54px;
        height: 54px;
        border-radius: 14px;
        object-fit: contain;
        background: rgba(255,255,255,0.03);
        padding: 6px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .payroll-title {
        font-size: 2rem;
        font-weight: 800;
        margin-bottom: 0.15rem;
    }
    .payroll-subtitle {
        color: #a9a9a9;
        margin-bottom: 1rem;
        font-size: 1.02rem;
    }
    .payroll-card {
        padding: 1rem;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.03);
        margin-bottom: 1rem;
    }
    .payroll-small {
        font-size: 0.9rem;
        color: #9e9e9e;
    }
    .payroll-big {
        font-size: 1.35rem;
        font-weight: 700;
    }
    div[data-testid="stTabs"] button {
        font-size: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

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
            except Exception:
                return np.nan
        return series.apply(convert)

    def guess_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        cols = list(df.columns)
        norm_cols = [normalize_text(c) for c in cols]

        for cand in candidates:
            cand_n = normalize_text(cand)
            for c, cn in zip(cols, norm_cols):
                if cn == cand_n:
                    return c

        for cand in candidates:
            cand_n = normalize_text(cand)
            for c, cn in zip(cols, norm_cols):
                if cand_n in cn:
                    return c

        return None

    def ensure_numeric_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        df = df.copy()
        for c in columns:
            if c in df.columns:
                df[c] = safe_num_series(df[c])
        return df

    def format_money(x):
        try:
            return f"{float(x):,.2f}"
        except Exception:
            return str(x)

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
            target_bonus_col = bonus_col if bonus_col else "مكافأة عامة"
            if target_bonus_col not in df.columns:
                df[target_bonus_col] = 0.0
            df[target_bonus_col] = safe_num_series(df[target_bonus_col]).fillna(0) + float(global_bonus)

        if global_deduction != 0:
            target_deduction_col = deduction_col if deduction_col else "خصم عام"
            if target_deduction_col not in df.columns:
                df[target_deduction_col] = 0.0
            df[target_deduction_col] = safe_num_series(df[target_deduction_col]).fillna(0) + float(global_deduction)

        return df

    def apply_delivery_difference_rule(
        df: pd.DataFrame,
        orders_col: str,
        threshold: float,
        rate: float
    ) -> pd.DataFrame:
        df = df.copy()

        if orders_col not in df.columns:
            return df

        orders = safe_num_series(df[orders_col]).fillna(0)

        shortage_diff = np.where(orders < threshold, threshold - orders, 0)
        shortage_deduction = shortage_diff * rate

        excess_diff = np.where(orders > threshold, orders - threshold, 0)
        excess_bonus = excess_diff * rate

        df["فارق الطلبات الناقص"] = shortage_diff
        df["خصم فارق الطلبات"] = shortage_deduction
        df["فارق الطلبات الزائد"] = excess_diff
        df["إضافة فارق الطلبات"] = excess_bonus

        return df

    def recompute_payroll(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
        df = df.copy()

        base_col = mapping.get("base")
        extra_col = mapping.get("extra")
        total_col = mapping.get("total")
        net_col = mapping.get("net")

        if not base_col or base_col not in df.columns:
            return df

        base = safe_num_series(df[base_col]).fillna(0)

        extra = 0
        if extra_col and extra_col in df.columns:
            extra = safe_num_series(df[extra_col]).fillna(0)

        overage_bonus = (
            safe_num_series(df["إضافة فارق الطلبات"]).fillna(0)
            if "إضافة فارق الطلبات" in df.columns else 0
        )
        shortage_deduction = (
            safe_num_series(df["خصم فارق الطلبات"]).fillna(0)
            if "خصم فارق الطلبات" in df.columns else 0
        )

        total_deductions = shortage_deduction

        deduction_keys = [
            "advance",
            "keeta",
            "late",
            "fuel",
            "supervisor",
            "general_deduction",
        ]
        for key in deduction_keys:
            col = mapping.get(key)
            if col and col in df.columns:
                total_deductions = total_deductions + safe_num_series(df[col]).fillna(0)

        total_value = base + extra + overage_bonus - total_deductions

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
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet_name, sheet_df in sheets_dict.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        output.seek(0)
        return output.getvalue()

    if "payroll_sheets" not in st.session_state:
        st.session_state.payroll_sheets = {}
    if "payroll_original_sheets" not in st.session_state:
        st.session_state.payroll_original_sheets = {}
    if "payroll_loaded_file_name" not in st.session_state:
        st.session_state.payroll_loaded_file_name = None

    if "payroll_apply_diff_rule" not in st.session_state:
        st.session_state.payroll_apply_diff_rule = True
    if "payroll_order_threshold" not in st.session_state:
        st.session_state.payroll_order_threshold = 450.0
    if "payroll_difference_rate" not in st.session_state:
        st.session_state.payroll_difference_rate = 9.0
    if "payroll_global_bonus" not in st.session_state:
        st.session_state.payroll_global_bonus = 0.0
    if "payroll_global_deduction" not in st.session_state:
        st.session_state.payroll_global_deduction = 0.0

    h1, h2 = st.columns([0.08, 0.92])
    with h1:
        if LOGO_IMG.exists():
            st.image(str(LOGO_IMG), use_container_width=True)
    with h2:
        st.markdown('<div class="payroll-title">💼 مسير الرواتب</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="payroll-subtitle">إدارة الرواتب، التعديلات الجماعية، وفارق الطلبات لكل سائق.</div>',
            unsafe_allow_html=True
        )

    if HERO_IMG.exists():
        st.image(str(HERO_IMG), use_container_width=True)

    st.markdown("### 📂 ملف الرواتب")
    uploaded_file = st.file_uploader("ارفع ملف Excel الخاص بالرواتب", type=["xlsx"], key="payroll_uploader")

    if uploaded_file is None and enabled_files:
        for f in enabled_files:
            try:
                name = getattr(f, "name", "")
                if str(name).lower().endswith(".xlsx"):
                    uploaded_file = f
                    break
            except Exception:
                continue

    if uploaded_file is not None:
        current_name = getattr(uploaded_file, "name", "uploaded_payroll.xlsx")
        if st.session_state.payroll_loaded_file_name != current_name:
            sheets = load_excel(uploaded_file)
            st.session_state.payroll_original_sheets = {k: v.copy() for k, v in sheets.items()}
            st.session_state.payroll_sheets = {k: v.copy() for k, v in sheets.items()}
            st.session_state.payroll_loaded_file_name = current_name

    if not st.session_state.payroll_sheets:
        st.info("ارفع ملف Excel الخاص بالرواتب للبدء.")
        return

    sheet_names = list(st.session_state.payroll_sheets.keys())
    selected_sheet = st.selectbox("اختر الشيت", sheet_names, key="payroll_sheet_select")

    base_df = st.session_state.payroll_original_sheets[selected_sheet].copy()

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.markdown("### بيانات الشيت")
    with top_right:
        if st.button("إعادة ضبط الشيت الحالي", key="payroll_reset_sheet"):
            st.session_state.payroll_sheets[selected_sheet] = st.session_state.payroll_original_sheets[selected_sheet].copy()
            st.rerun()

    with st.expander("🔧 ربط الأعمدة", expanded=False):
        cols = [""] + list(base_df.columns)

        guessed_name = guess_column(base_df, ["اسم السائق", "اسم الموظف", "الاسم", "اسم"])
        guessed_orders = guess_column(base_df, ["عدد الطلبات", "عدد طلبات", "الطلبات"])
        guessed_base = guess_column(base_df, ["الراتب الأساسي", "الراتب الاساسي", "راتب أساسي", "راتب اساسي"])
        guessed_extra = guess_column(base_df, ["اضافي", "إضافي", "بونس", "مكافأة"])
        guessed_advance = guess_column(base_df, ["سلفيات", "سلفية", "سلفة"])
        guessed_keeta = guess_column(base_df, ["خصم كيتا"])
        guessed_late = guess_column(base_df, ["تأخير"])
        guessed_fuel = guess_column(base_df, ["بنزين"])
        guessed_supervisor = guess_column(base_df, ["محاضر مشرف"])
        guessed_total = guess_column(base_df, ["اجمالي الراتب المستحق", "إجمالي الراتب المستحق", "الاجمالي"])
        guessed_net = guess_column(base_df, ["الصافي", "صافي"])

        name_col = st.selectbox("عمود الاسم", cols, index=cols.index(guessed_name) if guessed_name in cols else 0, key="payroll_name_col")
        orders_col = st.selectbox("عمود عدد الطلبات", cols, index=cols.index(guessed_orders) if guessed_orders in cols else 0, key="payroll_orders_col")
        base_col = st.selectbox("عمود الراتب الأساسي", cols, index=cols.index(guessed_base) if guessed_base in cols else 0, key="payroll_base_col")
        extra_col = st.selectbox("عمود الإضافي / المكافأة", cols, index=cols.index(guessed_extra) if guessed_extra in cols else 0, key="payroll_extra_col")
        advance_col = st.selectbox("عمود سلفيات", cols, index=cols.index(guessed_advance) if guessed_advance in cols else 0, key="payroll_advance_col")
        keeta_col = st.selectbox("عمود خصم كيتا", cols, index=cols.index(guessed_keeta) if guessed_keeta in cols else 0, key="payroll_keeta_col")
        late_col = st.selectbox("عمود تأخير", cols, index=cols.index(guessed_late) if guessed_late in cols else 0, key="payroll_late_col")
        fuel_col = st.selectbox("عمود بنزين", cols, index=cols.index(guessed_fuel) if guessed_fuel in cols else 0, key="payroll_fuel_col")
        supervisor_col = st.selectbox("عمود محاضر مشرف", cols, index=cols.index(guessed_supervisor) if guessed_supervisor in cols else 0, key="payroll_supervisor_col")
        total_col = st.selectbox("عمود الإجمالي", cols, index=cols.index(guessed_total) if guessed_total in cols else 0, key="payroll_total_col")
        net_col = st.selectbox("عمود الصافي", cols, index=cols.index(guessed_net) if guessed_net in cols else 0, key="payroll_net_col")

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
        "general_deduction": "خصم عام",
    }

    tab_config, tab_table, tab_driver, tab_export = st.tabs(
        ["⚙️ الإعدادات", "📋 الجدول", "👤 تفاصيل السائق", "⬇️ التصدير"]
    )

    with tab_config:
        st.markdown("### ⚙️ إعدادات الرواتب")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### إعدادات فارق الطلبات")
            st.session_state.payroll_apply_diff_rule = st.toggle(
                "تفعيل قاعدة فارق الطلبات",
                value=st.session_state.payroll_apply_diff_rule,
                key="payroll_cfg_apply_diff_rule"
            )

            st.session_state.payroll_order_threshold = st.number_input(
                "الحد المطلوب لعدد الطلبات",
                min_value=0.0,
                value=float(st.session_state.payroll_order_threshold),
                step=10.0,
                key="payroll_cfg_order_threshold"
            )

            st.session_state.payroll_difference_rate = st.number_input(
                "سعر فارق الطلبات",
                min_value=0.0,
                value=float(st.session_state.payroll_difference_rate),
                step=1.0,
                key="payroll_cfg_difference_rate"
            )

        with c2:
            st.markdown("#### التعديلات الجماعية")
            st.session_state.payroll_global_bonus = st.number_input(
                "مكافأة جماعية لكل الموظفين",
                min_value=0.0,
                value=float(st.session_state.payroll_global_bonus),
                step=50.0,
                key="payroll_cfg_global_bonus"
            )

            st.session_state.payroll_global_deduction = st.number_input(
                "خصم جماعي لكل الموظفين",
                min_value=0.0,
                value=float(st.session_state.payroll_global_deduction),
                step=50.0,
                key="payroll_cfg_global_deduction"
            )

        st.markdown("### المعاينة الحالية")
        v1, v2, v3, v4 = st.columns(4)

        with v1:
            st.metric("حد الطلبات", format_money(st.session_state.payroll_order_threshold))
        with v2:
            st.metric("سعر الفارق", format_money(st.session_state.payroll_difference_rate))
        with v3:
            st.metric("مكافأة جماعية", format_money(st.session_state.payroll_global_bonus))
        with v4:
            st.metric("خصم جماعي", format_money(st.session_state.payroll_global_deduction))

        st.info(
            f"إذا كان عدد الطلبات أقل من {format_money(st.session_state.payroll_order_threshold)} "
            f"فسيتم احتساب خصم فارق الطلبات = (الحد - عدد الطلبات) × {format_money(st.session_state.payroll_difference_rate)}. "
            f"وإذا كان عدد الطلبات أعلى من {format_money(st.session_state.payroll_order_threshold)} "
            f"فسيتم احتساب إضافة فارق الطلبات = (عدد الطلبات - الحد) × {format_money(st.session_state.payroll_difference_rate)}."
        )

    df = base_df.copy()

    numeric_cols = [
        c for c in [
            orders_col, base_col, extra_col, advance_col, keeta_col,
            late_col, fuel_col, supervisor_col, total_col, net_col
        ] if c
    ]
    df = ensure_numeric_columns(df, numeric_cols)

    if base_col and base_col in df.columns:
        df["الراتب الأساسي الأصلي"] = safe_num_series(df[base_col]).fillna(0)

    df = apply_global_adjustments(
        df=df,
        bonus_col=extra_col if extra_col else "مكافأة عامة",
        deduction_col="خصم عام",
        global_bonus=st.session_state.payroll_global_bonus,
        global_deduction=st.session_state.payroll_global_deduction
    )

    if st.session_state.payroll_apply_diff_rule and orders_col:
        df = apply_delivery_difference_rule(
            df=df,
            orders_col=orders_col,
            threshold=st.session_state.payroll_order_threshold,
            rate=st.session_state.payroll_difference_rate
        )

    df = recompute_payroll(df, mapping)

    st.markdown("### 📊 الملخص")
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("عدد الموظفين", len(df))

    with m2:
        if orders_col and orders_col in df.columns:
            st.metric("مجموع الطلبات", format_money(safe_num_series(df[orders_col]).fillna(0).sum()))
        else:
            st.metric("مجموع الطلبات", "—")

    with m3:
        if total_col and total_col in df.columns:
            st.metric("مجموع الإجمالي", format_money(safe_num_series(df[total_col]).fillna(0).sum()))
        else:
            st.metric("مجموع الإجمالي", "—")

    with m4:
        if net_col and net_col in df.columns:
            st.metric("مجموع الصافي", format_money(safe_num_series(df[net_col]).fillna(0).sum()))
        else:
            st.metric("مجموع الصافي", "—")

    with tab_table:
        st.markdown("### ✍️ تعديل الجدول")

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"payroll_editor_{selected_sheet}"
        )

        st.session_state.payroll_sheets[selected_sheet] = edited_df.copy()

    with tab_driver:
        st.markdown("### 👤 تفاصيل السائق")

        current_df = st.session_state.payroll_sheets[selected_sheet].copy()

        if name_col and name_col in current_df.columns:
            driver_names = current_df[name_col].fillna("").astype(str).tolist()
            selected_driver = st.selectbox("اختر السائق", driver_names, key="payroll_driver_select")

            driver_row = current_df[current_df[name_col].astype(str) == str(selected_driver)]

            if not driver_row.empty:
                row = driver_row.iloc[0]

                a, b, c = st.columns(3)

                with a:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.markdown('<div class="payroll-small">الاسم</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="payroll-big">{row.get(name_col, "")}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                with b:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.markdown('<div class="payroll-small">عدد الطلبات</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="payroll-big">{format_money(row.get(orders_col, 0) if orders_col else 0)}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                with c:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.markdown('<div class="payroll-small">الراتب الأساسي</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="payroll-big">{format_money(row.get(base_col, 0) if base_col else 0)}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                d1, d2, d3 = st.columns(3)

                with d1:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.write(f"**سلفيات:** {format_money(row.get(advance_col, 0) if advance_col else 0)}")
                    st.write(f"**خصم كيتا:** {format_money(row.get(keeta_col, 0) if keeta_col else 0)}")
                    st.write(f"**تأخير:** {format_money(row.get(late_col, 0) if late_col else 0)}")
                    st.markdown('</div>', unsafe_allow_html=True)

                with d2:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.write(f"**بنزين:** {format_money(row.get(fuel_col, 0) if fuel_col else 0)}")
                    st.write(f"**محاضر مشرف:** {format_money(row.get(supervisor_col, 0) if supervisor_col else 0)}")
                    st.write(f"**إضافي / مكافأة:** {format_money(row.get(extra_col, 0) if extra_col else 0)}")
                    st.markdown('</div>', unsafe_allow_html=True)

                with d3:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.write(f"**فارق الطلبات الناقص:** {format_money(row.get('فارق الطلبات الناقص', 0))}")
                    st.write(f"**خصم فارق الطلبات:** {format_money(row.get('خصم فارق الطلبات', 0))}")
                    st.write(f"**فارق الطلبات الزائد:** {format_money(row.get('فارق الطلبات الزائد', 0))}")
                    st.write(f"**إضافة فارق الطلبات:** {format_money(row.get('إضافة فارق الطلبات', 0))}")
                    st.write(f"**خصم عام:** {format_money(row.get('خصم عام', 0))}")
                    st.markdown('</div>', unsafe_allow_html=True)

                e1, e2 = st.columns(2)

                with e1:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.write(f"**الإجمالي:** {format_money(row.get(total_col, 0) if total_col else 0)}")
                    st.markdown('</div>', unsafe_allow_html=True)

                with e2:
                    st.markdown('<div class="payroll-card">', unsafe_allow_html=True)
                    st.write(f"**الصافي:** {format_money(row.get(net_col, 0) if net_col else 0)}")
                    st.markdown('</div>', unsafe_allow_html=True)

                with st.expander("عرض كل بيانات السائق"):
                    all_data = pd.DataFrame({
                        "الحقل": current_df.columns,
                        "القيمة": [row[col] for col in current_df.columns]
                    })
                    st.dataframe(all_data, use_container_width=True, hide_index=True)
        else:
            st.info("اختر عمود الاسم من قسم ربط الأعمدة لعرض تفاصيل السائق.")

    with tab_export:
        st.markdown("### ⬇️ تنزيل الملف")

        excel_data = to_excel_bytes(st.session_state.payroll_sheets)

        st.download_button(
            label="تنزيل ملف الرواتب المعدل",
            data=excel_data,
            file_name="مسير_الرواتب_المعدل.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="payroll_download_btn"
        )