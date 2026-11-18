# Smart Barangay Appointment Scheduling and Document Processing Information System

Streamlit + SQLite classroom prototype with two roles: Resident and Barangay Administrator/Staff.

## Included functions
### Resident
- Register and log in
- View active barangay services
- Schedule appointments and submit document requests
- Upload supporting requirements (PDF/JPG/PNG, max 10 MB per file)
- Track request status and uploaded files
- Receive in-app notifications
- View and export appointment history

### Administrator / Staff
- Log in to admin dashboard
- Add, activate, or deactivate barangay services
- View/manage appointment schedules
- Review document requests and download uploaded requirements
- Verify requirements and update processing status
- Approve, reject, or mark requests ready for claiming/completed
- Notify residents when status changes
- View charts and export reports

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

Demo admin credentials: `admin` / `admin12345`. Change before any real use.

## GitHub and Streamlit Community Cloud
Upload `app.py`, `requirements.txt`, `README.md`, `.gitignore`, and `uploads/.gitkeep` to a GitHub repository. In Streamlit Community Cloud, create an app from that repository, branch `main`, file `app.py`.

## Important limitations
This is an educational prototype, not an official government system. It uses local SQLite and a local uploads folder. Local files may not persist reliably on Streamlit Community Cloud across restarts/redeployments, and multiple cloud instances may not share them. For production, use a managed persistent database and private object storage, HTTPS, role provisioning, audit logs, backups, file scanning, access controls, privacy notices, retention rules, and barangay-approved workflows. Do not upload real resident personal data or sensitive documents to a public classroom demo. Confirm actual requirements, fees, schedules, and issuance rules with the barangay.
