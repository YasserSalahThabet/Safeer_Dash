import streamlit as st

from core.config import LEFT_IMG, RIGHT_IMG
from core.db import get_latest_announcements, add_announcement, delete_announcement


def render_header():
    cimg1, cimg2 = st.columns([1, 1])
    with cimg1:
        if RIGHT_IMG.exists():
            st.image(str(RIGHT_IMG), use_container_width=True)
    with cimg2:
        if LEFT_IMG.exists():
            st.image(str(LEFT_IMG), use_container_width=True)

    st.markdown("# لوحة سفير - Safeer Dash")
    st.markdown(
        '<div class="safeer-subtitle">الإدارة / التشغيل / الموارد البشرية / الإشراف / السيارات / الحسابات / مسير الرواتب</div>',
        unsafe_allow_html=True
    )
    st.divider()


def sidebar_controls(role: str):
    with st.sidebar:
        st.markdown(f"### المستخدم الحالي: {role}")
        st.divider()

        uploaded_files = st.file_uploader(
            label="تحميل ملفات",
            type=["xlsx"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )

        enabled_files = []
        if uploaded_files:
            with st.expander("📄 الملفات المرفوعة", expanded=False):
                st.caption("✅ فعّل الملف الذي تريد أن يقرأه النظام. أزل التفعيل لتعطيله.")
                for i, uf in enumerate(uploaded_files):
                    key = f"file_enable_{i}_{uf.name}"
                    if key not in st.session_state:
                        st.session_state[key] = True
                    checked = st.checkbox(uf.name, value=st.session_state[key], key=key)
                    if checked:
                        enabled_files.append(uf)
                st.caption(f"الملفات المفعّلة: {len(enabled_files)} / {len(uploaded_files)}")

        st.divider()
        search = st.text_input("بحث (المعرف / الاسم)", "")
        min_delivery = st.slider("أقل معدل توصيل", 0.0, 1.0, 0.0, 0.01)
        max_cancel = st.slider("أعلى معدل إلغاء (فلترة)", 0.0, 1.0, 1.0, 0.01)

    return uploaded_files, enabled_files, search, min_delivery, max_cancel


def sidebar_announcements(role: str):
    can_manage = role in ("الإدارة", "التشغيل")  # everyone sees; only these manage

    with st.sidebar:
        st.divider()
        with st.expander("📢 الإعلانات", expanded=False):
            ann_df = get_latest_announcements(limit=10)

            if len(ann_df):
                for _, r in ann_df.iterrows():
                    st.caption(f"{r['created_at']} — {r['created_by_role']}")
                    st.write(r["message"])

                    if can_manage:
                        if st.button("🗑️ حذف", key=f"del_ann_{int(r['id'])}"):
                            delete_announcement(int(r["id"]))
                            st.rerun()

                    st.markdown("---")
            else:
                st.caption("لا توجد إعلانات بعد.")

            if can_manage:
                ann_text = st.text_area(
                    "إرسال إعلان",
                    placeholder="اكتب الإعلان هنا...",
                    label_visibility="collapsed",
                    height=80
                )
                if st.button("إرسال", use_container_width=True):
                    add_announcement(ann_text, role)
                    st.rerun()
            else:
                st.caption("يمكن للإدارة والتشغيل فقط إضافة/حذف الإعلانات.")
