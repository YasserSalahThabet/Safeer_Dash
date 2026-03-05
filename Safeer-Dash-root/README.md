# Safeer Dash (Streamlit)

## Run locally (Windows CMD)
```bat
cd Safeer-Dash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Passwords
- Default password for all roles is **12345** if Streamlit secrets are not configured.

If you deploy on Streamlit Cloud:
- Add secrets in **App settings → Secrets**.

Example:
```toml
[auth]
admin_password = "12345"
ops_password = "12345"
hr_password = "12345"
sup_password = "12345"
fleet_password = "12345"
accounts_password = "12345"
payroll_password = "12345"
```

## Roles
- الإدارة
- التشغيل
- الموارد البشرية
- الإشراف
- السيارات / الحركة
- الحسابات
- مسير الرواتب
