# Student & Staff Attendance Management System

A Streamlit attendance system with:
- Student login
- Staff login
- Live face embedding verification
- Browser GPS validation
- Google Sheets storage
- Present / Pending / Absent workflows
- Staff reports and exports

## Important security note
If you ever pasted a service-account private key into chat or a public place, revoke that key immediately and create a new one in Google Cloud.

## Install Python
Install Python 3.11.

Check:
```bash
python --version
```

## Create a virtual environment

### Windows
```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Install dependencies
```bash
pip install -r requirements.txt
```

## Google Cloud setup
1. Create a Google Cloud project.
2. Enable **Google Sheets API**.
3. Create a **Service Account**.
4. Download the **JSON key**.
5. Create one Google Sheet.
6. Share the sheet with the service-account email.

## Sheet structure
Create these worksheets:
- Students
- Staff
- Attendance
- Reports
- Settings

The app will create headers automatically on first run.

## Streamlit secrets
Create `.streamlit/secrets.toml`.

Use the Google Sheet **ID** or the full Google Sheet URL. The app accepts both.

Example:
```toml
google_sheet_id = "YOUR_SHEET_ID"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----"""
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

## Run locally
```bash
streamlit run app.py
```

## Deploy to Streamlit Community Cloud
1. Push to GitHub.
2. Create a new Streamlit app.
3. Point it to `app.py`.
4. Add secrets in Streamlit Cloud.
5. Redeploy.

## How attendance works
Student:
1. Log in with username / roll number and password.
2. Capture selfie.
3. Face embedding is generated and compared.
4. Browser GPS is read.
5. If face and location both match, attendance is stored in Google Sheets.

Stored fields:
- roll number
- name
- date
- time
- latitude
- longitude
- distance
- present / absent

## Troubleshooting
- If install fails, confirm `runtime.txt` is `python-3.11`.
- If Google Sheets fails, verify the sheet is shared with the service account email.
- If camera fails, allow camera permission.
- If GPS fails, allow location permission and use HTTPS on deployment.
- If face recognition is slow on first load, wait for the model to download once.
