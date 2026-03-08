from __future__ import annotations

from io import BytesIO
import pandas as pd
import numpy as np
import streamlit as st

from core.db import upsert_driver

CANCEL_ALERT_THRESHOLD = 0.002  # 0.20% (alert if >=)
ORDERS_TARGET_MONTH = 450


# =========================
# Column mappings
# =========================
PERF_COLS = {
    "driver_id": [
        "معرّف السائق", "معرف السائق", "Driver_ID", "driver_id", "id", "ID",
        "rider Id", "rider_id", "courier_id"
    ],
    "first_name": ["اسم السائق", "First Name", "first_name", "الاسم الأول", "اسم الموظف"],
    "last_name": ["اسم السائق.1", "Last Name", "last_name", "الاسم الأخير", "اسم الموظف.1"],
    "full_name": ["اسم السائق الكامل", "اسم الموظف", "Driver Name", "driver_name", "اسم السائق", "Driver_Name"],

    "delivery_rate": [
        "معدل اكتمال الطلبات (غير متعلق بالتوصيل)",
        "معدل التوصيل", "معدل توصيل", "Delivery_Rate", "delivery_rate", "Delivery rate"
    ],
    "cancel_rate": [
        "معدل الإلغاء بسبب مشاكل التوصيل",
        "معدل غاء", "معدل الغاء", "معدل الإلغاء", "Cancel_Rate", "cancel_rate", "Cancel rate"
    ],
    "orders_delivered": [
        "المهام التي تم تسليمها", "طلبات", "الطلبات", "الطلبات المسلمة",
        "Orders_Delivered", "orders_delivered", "عدد الطلبات"
    ],
    "reject_total": [
        "المهام المرفوضة", "المهام المرفوضة (السائق)",
        "رفض السائق", "Driver Rejections", "driver_rejections"
    ],

    "work_days": ["اعدد ايام العمل", "عدد ايام العمل", "أيام العمل", "days_worked", "Work Days"],

    # keep exact names requested
    "vr": ["VR", "vr", "if_triggered_today", "is_self_delivery_final"],
    "vda": ["VDA", "vda", "مؤشر VDA", "VDA Score", "VDA%", "VDA %", "VDA score"],
}

VRVDA_COLS = {
    "driver_id": PERF_COLS["driver_id"],
    "vr": PERF_COLS["vr"],
    "vda": PERF_COLS["vda"],
}


# =========================
# Helpers
# =========================
def normalize_col(c: object) -> str:
    return str(c).strip()


def pick(df_cols, candidates) -> str | None:
    cols = [normalize_col(c) for c in df_cols]
    for cand in candidates:
        if cand in cols:
            return cand
    return None


@st.cache_data(show_spinner=False)
def read_first_sheet_excel_bytes(file_bytes: bytes, header: int | None = 0) -> pd.DataFrame:
    bio = BytesIO(file_bytes)
    xls = pd.ExcelFile(bio)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(bio, sheet_name=sheet, header=header)
    df.columns = [normalize_col(c) for c in df.columns]
    return df


def safe_to_numeric(s):
    return pd.to_numeric(s, errors="coerce")


def _name_with_space(first: str, last: str) -> str:
    first = (first or "").strip()
    last = (last or "").strip()
    full = f"{first} {last}".strip()
    return " ".join(full.split())


def _fmt_int(x):
    try:
        if pd.isna(x):
            return ""
        return f"{int(round(float(x))):,}"
    except Exception:
        return x


def _normalize_vr_series(s: pd.Series) -> pd.Series:
    """
    Convert common VR-like values into numeric:
    yes/true/pass -> 1
    no/false/fail -> 0
    numeric strings stay numeric
    """
    if s is None:
        return pd.Series(dtype="float64")

    raw = s.copy()

    numeric = pd.to_numeric(raw, errors="coerce")

    txt = raw.astype(str).str.strip().str.lower()
    mapped = txt.map({
        "pass": 1,
        "passed": 1,
        "true": 1,
        "yes": 1,
        "y": 1,
        "1": 1,

        "fail": 0,
        "failed": 0,
        "false": 0,
        "no": 0,
        "n": 0,
        "0": 0
    })

    return numeric.fillna(mapped)


# =========================
# File detection
# =========================
def detect_file_kind(cols: set[str]) -> str:
    perf_signals = {
        "معرّف السائق", "معرف السائق", "اسم السائق", "اسم السائق.1", "Driver_Name",
        "معدل الإلغاء بسبب مشاكل التوصيل", "معدل الغاء", "معدل توصيل",
        "المهام التي تم تسليمها", "طلبات", "المهام المرفوضة",
        "المهام المرفوضة (السائق)", "عدد الطلبات",
    }

    vrvda_signals = {
        "VR", "vr", "if_triggered_today", "is_self_delivery_final",
        "VDA", "vda", "مؤشر VDA", "VDA Score", "VDA%", "VDA %", "VDA score"
    }

    if len(perf_signals.intersection(cols)) >= 3:
        return "performance"
    if len(vrvda_signals.intersection(cols)) >= 1:
        return "vrvda"
    return "unknown"


# =========================
# Performance parsing
# =========================
def parse_performance(df_raw: pd.DataFrame) -> pd.DataFrame:
    mapped = {k: pick(df_raw.columns, v) for k, v in PERF_COLS.items()}

    id_col = mapped.get("driver_id")
    delivery_col = mapped.get("delivery_rate")
    cancel_col = mapped.get("cancel_rate")
    orders_col = mapped.get("orders_delivered")
    reject_col = mapped.get("reject_total")

    missing = []
    if not id_col:
        missing.append("driver_id")
    if not delivery_col:
        missing.append("delivery_rate")
    if not cancel_col:
        missing.append("cancel_rate")
    if not orders_col:
        missing.append("orders_delivered")
    if not reject_col:
        missing.append("reject_total")
    if missing:
        raise ValueError(", ".join(missing))

    first_col = mapped.get("first_name")
    last_col = mapped.get("last_name")
    full_col = mapped.get("full_name")

    if first_col and last_col and first_col in df_raw.columns and last_col in df_raw.columns:
        driver_name = [
            _name_with_space(str(a) if pd.notna(a) else "", str(b) if pd.notna(b) else "")
            for a, b in zip(df_raw[first_col], df_raw[last_col])
        ]
        driver_name = pd.Series(driver_name)
    elif full_col and full_col in df_raw.columns:
        driver_name = df_raw[full_col].astype(str).map(lambda x: " ".join(str(x).split())).fillna("")
    elif first_col and first_col in df_raw.columns:
        driver_name = df_raw[first_col].astype(str).map(lambda x: " ".join(str(x).split())).fillna("")
    else:
        driver_name = pd.Series([""] * len(df_raw))

    out = pd.DataFrame({
        "معرّف السائق": safe_to_numeric(df_raw[id_col]).astype("Int64"),
        "اسم السائق": driver_name.astype(str).map(lambda x: " ".join(str(x).split())),
        "معدل توصيل": safe_to_numeric(df_raw[delivery_col]).fillna(0).clip(0, 1),
        "معدل الغاء": safe_to_numeric(df_raw[cancel_col]).fillna(0).clip(0, 1),
        "طلبات": safe_to_numeric(df_raw[orders_col]).fillna(0),
        "المهام المرفوضة": safe_to_numeric(df_raw[reject_col]).fillna(0),
    })

    if mapped.get("work_days") and mapped["work_days"] in df_raw.columns:
        out["اعدد ايام العمل"] = safe_to_numeric(df_raw[mapped["work_days"]]).fillna(0)
    else:
        out["اعدد ايام العمل"] = pd.NA

    # Optional VR / VDA if already in performance file
    if mapped.get("vr") and mapped["vr"] in df_raw.columns:
        out["VR"] = _normalize_vr_series(df_raw[mapped["vr"]]).fillna(0)
    else:
        out["VR"] = pd.NA

    if mapped.get("vda") and mapped["vda"] in df_raw.columns:
        out["VDA"] = safe_to_numeric(df_raw[mapped["vda"]]).fillna(0)
    else:
        out["VDA"] = pd.NA

    return out


# =========================
# VR / VDA parsing
# =========================
def parse_vrvda(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Supports:
    - standard header files with rider/courier/driver id
    - weird no-header VDA export
    Match ONLY by rider/driver ID
    Ignore city / 3PL / company columns
    """
    id_col = pick(df_raw.columns, VRVDA_COLS["driver_id"])
    vr_col = pick(df_raw.columns, VRVDA_COLS["vr"])
    vda_col = pick(df_raw.columns, VRVDA_COLS["vda"])

    # -------- Standard header format --------
    if id_col and (vr_col or vda_col):
        tmp = pd.DataFrame({
            "معرّف السائق": safe_to_numeric(df_raw[id_col]).astype("Int64")
        })

        if vr_col:
            tmp["VR"] = _normalize_vr_series(df_raw[vr_col])

        if vda_col:
            tmp["VDA"] = safe_to_numeric(df_raw[vda_col])

        tmp = tmp.dropna(subset=["معرّف السائق"]).copy()

        # aggregate to ONE row per driver
        agg_map = {}
        if "VR" in tmp.columns:
            # sum positive hits so you see actual numbers
            agg_map["VR"] = "sum"
        if "VDA" in tmp.columns:
            # use max/latest-like numeric strength
            agg_map["VDA"] = "max"

        tmp = tmp.groupby("معرّف السائق", as_index=False).agg(agg_map)
        return tmp

    # -------- No-header / weird export --------
    # common pattern in your file:
    # col 6 = rider/driver id
    # col 9 = VDA numeric
    # col 8 may be VR-like
    if all(isinstance(c, (int, np.integer)) for c in df_raw.columns):
        id_candidates = [6, 1]   # prefer rider id in col 6, fallback to old logic col 1
        id_col_num = next((c for c in id_candidates if c in df_raw.columns), None)

        if id_col_num is not None:
            tmp = pd.DataFrame({
                "معرّف السائق": safe_to_numeric(df_raw[id_col_num]).astype("Int64")
            })

            if 8 in df_raw.columns:
                tmp["VR"] = safe_to_numeric(df_raw[8], errors="coerce")

            if 9 in df_raw.columns:
                tmp["VDA"] = safe_to_numeric(df_raw[9], errors="coerce")

            tmp = tmp.dropna(subset=["معرّف السائق"]).copy()

            agg_map = {}
            if "VR" in tmp.columns:
                agg_map["VR"] = "sum"
            if "VDA" in tmp.columns:
                agg_map["VDA"] = "max"

            if agg_map:
                tmp = tmp.groupby("معرّف السائق", as_index=False).agg(agg_map)
                return tmp

    return pd.DataFrame(columns=["معرّف السائق", "VR", "VDA"])


# =========================
# Styling
# =========================
def style_attention_table(df: pd.DataFrame):
    sty = df.style.format({
        "معدل توصيل": "{:.2%}",
        "معدل الغاء": "{:.2%}",
        "طلبات": _fmt_int,
        "المهام المرفوضة": _fmt_int,
    })
    sty = sty.applymap(
        lambda x: "color:red;font-weight:900;" if float(x) >= CANCEL_ALERT_THRESHOLD else "",
        subset=["معدل الغاء"]
    )
    sty = sty.applymap(
        lambda x: "color:red;font-weight:900;" if float(x) < 1.0 else "",
        subset=["معدل توصيل"]
    )
    sty = sty.applymap(
        lambda x: "color:red;font-weight:900;" if float(x) < ORDERS_TARGET_MONTH else "",
        subset=["طلبات"]
    )
    sty = sty.applymap(
        lambda x: "color:red;font-weight:900;" if float(x) > 0 else "",
        subset=["المهام المرفوضة"]
    )
    return sty


# =========================
# Master builder
# =========================
def build_master_from_uploads(enabled_files, search: str, min_delivery: float, max_cancel: float):
    if not enabled_files:
        return None, None

    file_items = []
    for uf in enabled_files:
        b = uf.getvalue()

        # normal header first
        df_h = read_first_sheet_excel_bytes(b, header=0)
        kind = detect_file_kind(set(df_h.columns))
        df_use = df_h

        # no-header fallback for weird VR/VDA exports
        if kind == "unknown":
            df_nh = read_first_sheet_excel_bytes(b, header=None)
            if all(isinstance(c, (int, np.integer)) for c in df_nh.columns):
                kind = "vrvda"
                df_use = df_nh

        file_items.append({
            "name": uf.name,
            "df": df_use,
            "kind": kind
        })

    perf_item = next((x for x in file_items if x["kind"] == "performance"), None)
    if perf_item is None:
        return None, None

    try:
        perf = parse_performance(perf_item["df"])
    except ValueError as e:
        st.error("❌ ملف الأداء غير مطابق. الأعمدة المطلوبة غير موجودة: " + str(e))
        st.write("الأعمدة الموجودة في الملف:")
        st.write(list(perf_item["df"].columns))
        st.stop()

    # Update DB with names
    for _, r in perf.iterrows():
        did = r.get("معرّف السائق")
        name = r.get("اسم السائق")
        if pd.isna(did):
            continue
        upsert_driver(int(did), driver_name=str(name))

    master = perf.copy()

    # Merge VR / VDA from separate files
    for item in file_items:
        if item["name"] == perf_item["name"]:
            continue
        if item["kind"] != "vrvda":
            continue

        vrvda = parse_vrvda(item["df"])
        if len(vrvda):
            master = master.merge(vrvda, on="معرّف السائق", how="left", suffixes=("", "_y"))

            if "VR_y" in master.columns:
                if "VR" in master.columns:
                    master["VR"] = master["VR"].fillna(master["VR_y"])
                else:
                    master["VR"] = master["VR_y"]
                master = master.drop(columns=["VR_y"])

            if "VDA_y" in master.columns:
                if "VDA" in master.columns:
                    master["VDA"] = master["VDA"].fillna(master["VDA_y"])
                else:
                    master["VDA"] = master["VDA_y"]
                master = master.drop(columns=["VDA_y"])

    if "VR" in master.columns:
        master["VR"] = pd.to_numeric(master["VR"], errors="coerce").fillna(0)
    else:
        master["VR"] = pd.NA

    if "VDA" in master.columns:
        master["VDA"] = pd.to_numeric(master["VDA"], errors="coerce").fillna(0)
    else:
        master["VDA"] = pd.NA

    f = master.copy()

    # filters
    if search.strip():
        s = search.strip().lower()
        f = f[
            f["اسم السائق"].astype(str).str.lower().str.contains(s, na=False)
            | f["معرّف السائق"].astype(str).str.contains(s, na=False)
        ]

    f = f[(f["معدل توصيل"] >= float(min_delivery))]
    f = f[(f["معدل الغاء"] <= float(max_cancel))]

    # priority
    f["تنبيه الغاء"] = (f["معدل الغاء"] >= CANCEL_ALERT_THRESHOLD).astype(int)
    f["تنبيه توصيل"] = (f["معدل توصيل"] < 1.0).astype(int)
    f["تنبيه طلبات"] = (
        pd.to_numeric(f["طلبات"], errors="coerce").fillna(0) < ORDERS_TARGET_MONTH
    ).astype(int)
    f["تنبيه رفض"] = (
        pd.to_numeric(f["المهام المرفوضة"], errors="coerce").fillna(0) > 0
    ).astype(int)

    delivery_gap = (1.0 - f["معدل توصيل"]).clip(lower=0)
    cancel_over = (f["معدل الغاء"] - CANCEL_ALERT_THRESHOLD).clip(lower=0)
    orders_gap = (
        ORDERS_TARGET_MONTH - pd.to_numeric(f["طلبات"], errors="coerce").fillna(0)
    ).clip(lower=0)

    f["أولوية"] = (
        f["تنبيه الغاء"] * 1_000_000
        + cancel_over * 500_000
        + delivery_gap * 50_000
        + f["تنبيه طلبات"] * 10_000
        + orders_gap * 5
        + pd.to_numeric(f["المهام المرفوضة"], errors="coerce").fillna(0) * 200
    )

    f = f.sort_values(
        ["أولوية", "تنبيه الغاء", "معدل الغاء", "معدل توصيل", "طلبات", "المهام المرفوضة"],
        ascending=[False, False, False, True, True, False]
    ).reset_index(drop=True)

    f["ترتيب المتابعة"] = range(1, len(f) + 1)

    # Keep current app.py compatibility:
    # return filtered first, master second
    return f, master