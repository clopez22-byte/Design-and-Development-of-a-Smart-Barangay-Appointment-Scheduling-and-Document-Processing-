import streamlit as st
import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import date, datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Smart Barangay System", page_icon="🏛️", layout="wide")
BASE = Path(__file__).parent
DB_PATH = BASE / "barangay.db"
UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DEFAULT_SERVICES = [
    ("Barangay Clearance", "Certificate for employment, school, or other lawful purposes."),
    ("Certificate of Indigency", "Certification of indigency, subject to barangay verification."),
    ("Certificate of Residency", "Certification that a resident lives in the barangay."),
    ("Cedula / Community Tax Certificate", "Community tax-related service. Follow local issuing procedures."),
    ("Barangay Business Clearance", "Barangay-level business clearance, subject to local requirements."),
]
TIME_SLOTS = ["8:00 AM - 9:00 AM", "9:00 AM - 10:00 AM", "10:00 AM - 11:00 AM",
              "1:00 PM - 2:00 PM", "2:00 PM - 3:00 PM", "3:00 PM - 4:00 PM"]
SLOT_CAPACITY = 5
STATUSES = ["Pending", "Under Review", "Requirements Incomplete", "Approved", "Rejected", "Ready for Claiming", "Completed"]

def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def pw_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 150_000).hex()
    return salt + "$" + key

def pw_check(password, stored):
    try:
        salt, key = stored.split("$", 1)
        return secrets.compare_digest(pw_hash(password, salt).split("$", 1)[1], key)
    except Exception:
        return False

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
          username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'resident', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS services(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
          description TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          service_id INTEGER NOT NULL, purpose TEXT NOT NULL,
          appointment_date TEXT NOT NULL, time_slot TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Pending', admin_note TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id),
          FOREIGN KEY(service_id) REFERENCES services(id)
        );
        CREATE TABLE IF NOT EXISTS requirements(
          id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL,
          filename TEXT NOT NULL, stored_path TEXT NOT NULL,
          uploaded_at TEXT NOT NULL,
          FOREIGN KEY(request_id) REFERENCES requests(id)
        );
        CREATE TABLE IF NOT EXISTS notifications(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          request_id INTEGER, message TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        if not con.execute("SELECT id FROM users WHERE username='admin'").fetchone():
            con.execute("INSERT INTO users(full_name,username,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                        ("Barangay Administrator", "admin", pw_hash("admin12345"), "admin", datetime.now().isoformat(timespec="seconds")))
        for name, desc in DEFAULT_SERVICES:
            con.execute("INSERT OR IGNORE INTO services(name,description,active) VALUES(?,?,1)", (name, desc))

def get_user(username):
    with db() as con:
        return con.execute("SELECT * FROM users WHERE username=?", (username.strip().lower(),)).fetchone()

def register(name, username, password):
    with db() as con:
        con.execute("INSERT INTO users(full_name,username,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                    (name.strip(), username.strip().lower(), pw_hash(password), "resident", datetime.now().isoformat(timespec="seconds")))

def services(active_only=True):
    with db() as con:
        q = "SELECT * FROM services" + (" WHERE active=1" if active_only else "") + " ORDER BY name"
        return pd.read_sql_query(q, con)

def slots_left(day, slot):
    with db() as con:
        n = con.execute("SELECT COUNT(*) FROM requests WHERE appointment_date=? AND time_slot=? AND status NOT IN ('Rejected')",
                        (str(day), slot)).fetchone()[0]
    return max(0, SLOT_CAPACITY - n)

def create_request(user_id, service_id, purpose, day, slot):
    with db() as con:
        n = con.execute("SELECT COUNT(*) FROM requests WHERE appointment_date=? AND time_slot=? AND status!='Rejected'",
                        (str(day), slot)).fetchone()[0]
        if n >= SLOT_CAPACITY:
            return None
        cur = con.execute("""INSERT INTO requests(user_id,service_id,purpose,appointment_date,time_slot,status,created_at)
                          VALUES(?,?,?,?,?,'Pending',?)""",
                          (user_id, service_id, purpose.strip(), str(day), slot, datetime.now().isoformat(timespec="seconds")))
        rid = cur.lastrowid
        con.execute("INSERT INTO notifications(user_id,request_id,message,created_at) VALUES(?,?,?,?)",
                    (user_id, rid, f"Your request #{rid} was submitted and is pending review.", datetime.now().isoformat(timespec="seconds")))
        return rid

def resident_data(user_id):
    with db() as con:
        return pd.read_sql_query("""SELECT r.id AS 'Request ID', s.name AS 'Service',
          r.purpose AS 'Purpose', r.appointment_date AS 'Appointment Date',
          r.time_slot AS 'Time', r.status AS 'Status', r.admin_note AS 'Staff Note'
          FROM requests r JOIN services s ON s.id=r.service_id
          WHERE r.user_id=? ORDER BY r.id DESC""", con, params=(user_id,))

def request_data():
    with db() as con:
        return pd.read_sql_query("""SELECT r.id AS 'Request ID', u.full_name AS 'Resident',
          u.username AS 'Username', s.name AS 'Service', r.purpose AS 'Purpose',
          r.appointment_date AS 'Appointment Date', r.time_slot AS 'Time',
          r.status AS 'Status', r.admin_note AS 'Staff Note', r.user_id AS 'User ID'
          FROM requests r JOIN users u ON u.id=r.user_id
          JOIN services s ON s.id=r.service_id ORDER BY r.appointment_date DESC, r.id DESC""", con)

def notify(user_id, request_id, message):
    with db() as con:
        con.execute("INSERT INTO notifications(user_id,request_id,message,created_at) VALUES(?,?,?,?)",
                    (user_id, request_id, message, datetime.now().isoformat(timespec="seconds")))

def user_notifications(user_id):
    with db() as con:
        return pd.read_sql_query("SELECT id AS 'ID', message AS 'Notification', created_at AS 'Date', is_read FROM notifications WHERE user_id=? ORDER BY id DESC",
                                 con, params=(user_id,))

def mark_notifications_read(user_id):
    with db() as con:
        con.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))

def update_status(rid, user_id, status, note):
    with db() as con:
        con.execute("UPDATE requests SET status=?, admin_note=? WHERE id=?", (status, note, int(rid)))
    notify(user_id, int(rid), f"Update for request #{rid}: status is now '{status}'." + (f" Staff note: {note}" if note else ""))

def requirement_list(rid):
    with db() as con:
        return con.execute("SELECT * FROM requirements WHERE request_id=? ORDER BY id DESC", (int(rid),)).fetchall()

def add_requirement(rid, uploaded):
    safe_name = Path(uploaded.name).name.replace(" ", "_")
    stored_name = f"request_{rid}_{secrets.token_hex(5)}_{safe_name}"
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(uploaded.getbuffer())
    with db() as con:
        con.execute("INSERT INTO requirements(request_id,filename,stored_path,uploaded_at) VALUES(?,?,?,?)",
                    (int(rid), uploaded.name, str(dest), datetime.now().isoformat(timespec="seconds")))

def active_user_requests(user_id):
    with db() as con:
        return con.execute("SELECT id FROM requests WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()

init_db()
st.sidebar.title("🏛️ Smart Barangay")
st.sidebar.caption("Appointment Scheduling & Document Processing")

if "user_id" not in st.session_state:
    auth_page = st.sidebar.radio("Account", ["Login", "Register"])
    st.title("🏛️ Smart Barangay Appointment Scheduling and Document Processing")
    st.write("A prototype portal for residents and barangay personnel.")
    if auth_page == "Login":
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log in", use_container_width=True)
        if submit:
            u = get_user(username)
            if u and pw_check(password, u["password_hash"]):
                st.session_state.update(user_id=u["id"], username=u["username"], full_name=u["full_name"], role=u["role"])
                st.rerun()
            st.error("Invalid username or password.")
        st.info("Demo admin login: `admin` / `admin12345`. Change this before real use.")
    else:
        with st.form("register"):
            name = st.text_input("Full name")
            username = st.text_input("Create username")
            password = st.text_input("Create password (minimum 8 characters)", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submit = st.form_submit_button("Create resident account", use_container_width=True)
        if submit:
            if not name.strip() or not username.strip():
                st.error("Complete all fields.")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    register(name, username, password)
                    st.success("Account created. Please log in.")
                except sqlite3.IntegrityError:
                    st.error("That username is already in use.")
else:
    st.sidebar.write(f"**{st.session_state.full_name}**")
    st.sidebar.caption(st.session_state.role.title())
    if st.sidebar.button("Log out"):
        for k in ["user_id", "username", "full_name", "role"]:
            st.session_state.pop(k, None)
        st.rerun()

    if st.session_state.role == "resident":
        page = st.sidebar.radio("Resident Menu", ["Dashboard", "Available Services", "Book Appointment / Request Document", "Upload Requirements", "Track Requests", "Notifications", "Appointment History"])
        uid = st.session_state.user_id
        mine = resident_data(uid)
        if page == "Dashboard":
            st.title("Resident Dashboard")
            st.subheader(f"Welcome, {st.session_state.full_name}")
            x, y, z = st.columns(3)
            x.metric("Total Requests", len(mine))
            y.metric("Pending", int((mine.Status == "Pending").sum()) if not mine.empty else 0)
            z.metric("Approved", int(mine.Status.isin(["Approved", "Ready for Claiming", "Completed"]).sum()) if not mine.empty else 0)
            st.info("Choose a service, submit your request, upload supporting requirements, and monitor updates here.")
            st.subheader("Recent requests")
            st.dataframe(mine.head(5), use_container_width=True, hide_index=True)
        elif page == "Available Services":
            st.title("Available Barangay Services")
            svc = services()
            if svc.empty:
                st.info("No services are currently available.")
            for _, row in svc.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row['name']}**")
                    st.write(row["description"])
        elif page == "Book Appointment / Request Document":
            st.title("Book an Appointment and Request a Document")
            svc = services()
            if svc.empty:
                st.warning("There are no active services at the moment.")
            else:
                with st.form("new_request"):
                    chosen = st.selectbox("Select service", svc["name"].tolist())
                    purpose = st.text_area("Purpose of request")
                    first_day = date.today() + timedelta(days=1)
                    appt_day = st.date_input("Appointment date", value=first_day, min_value=first_day, max_value=date.today()+timedelta(days=60))
                    slot = st.selectbox("Appointment time", TIME_SLOTS)
                    remaining = slots_left(appt_day, slot)
                    st.caption(f"Remaining slots: {remaining} / {SLOT_CAPACITY}")
                    submit = st.form_submit_button("Submit appointment and request")
                if submit:
                    if not purpose.strip():
                        st.error("Please provide the purpose.")
                    else:
                        sid = int(svc.loc[svc["name"] == chosen, "id"].iloc[0])
                        rid = create_request(uid, sid, purpose, appt_day, slot)
                        if rid:
                            st.success(f"Request submitted successfully. Your Request ID is #{rid}.")
                            st.rerun()
                        else:
                            st.error("That appointment slot is full. Choose another.")
        elif page == "Upload Requirements":
            st.title("Upload Supporting Requirements")
            st.caption("Only upload documents requested by the barangay. Prototype limit: 10 MB per file.")
            reqs = active_user_requests(uid)
            if not reqs:
                st.info("Submit a document request first.")
            else:
                ids = [r["id"] for r in reqs]
                rid = st.selectbox("Select your request", ids, format_func=lambda x: f"Request #{x}")
                existing = requirement_list(rid)
                for f in existing:
                    st.write(f"📎 {f['filename']} — uploaded {f['uploaded_at']}")
                file = st.file_uploader("Choose a requirement file", type=["pdf", "png", "jpg", "jpeg"])
                if st.button("Upload file", disabled=file is None):
                    if file.size > 10 * 1024 * 1024:
                        st.error("File is larger than 10 MB.")
                    else:
                        add_requirement(rid, file)
                        st.success("Requirement uploaded.")
                        st.rerun()
        elif page == "Track Requests":
            st.title("Track Request Status")
            if mine.empty:
                st.info("You have no requests yet.")
            else:
                st.dataframe(mine[["Request ID", "Service", "Appointment Date", "Time", "Status", "Staff Note"]], use_container_width=True, hide_index=True)
                rid = st.selectbox("View uploaded requirements for request", mine["Request ID"].tolist())
                for f in requirement_list(rid):
                    st.write(f"📎 {f['filename']} — {f['uploaded_at']}")
        elif page == "Notifications":
            st.title("Notifications")
            notes = user_notifications(uid)
            unread = int((notes["is_read"] == 0).sum()) if not notes.empty else 0
            st.metric("Unread notifications", unread)
            if not notes.empty:
                st.dataframe(notes.drop(columns=["is_read"]), use_container_width=True, hide_index=True)
                if unread and st.button("Mark all as read"):
                    mark_notifications_read(uid)
                    st.rerun()
            else:
                st.info("No notifications yet.")
        else:
            st.title("Appointment History")
            if mine.empty:
                st.info("No appointment history yet.")
            else:
                st.dataframe(mine[["Request ID", "Service", "Appointment Date", "Time", "Status"]], use_container_width=True, hide_index=True)
                st.download_button("Download appointment history CSV", mine.to_csv(index=False).encode(), "appointment_history.csv", "text/csv")

    elif st.session_state.role == "admin":
        page = st.sidebar.radio("Administrator / Staff Menu", ["Admin Dashboard", "Manage Services", "Manage Appointment Schedules", "Review & Verify Requests", "Generate Reports"])
        data = request_data()
        if page == "Admin Dashboard":
            st.title("Barangay Administrator / Staff Dashboard")
            a,b,c,d = st.columns(4)
            a.metric("Total Requests", len(data))
            b.metric("Pending", int((data.Status == "Pending").sum()) if not data.empty else 0)
            c.metric("Under Review", int((data.Status == "Under Review").sum()) if not data.empty else 0)
            d.metric("Completed", int((data.Status == "Completed").sum()) if not data.empty else 0)
            st.subheader("Latest requests")
            st.dataframe(data.drop(columns=["User ID"]).head(10), use_container_width=True, hide_index=True)
        elif page == "Manage Services":
            st.title("Manage Barangay Services")
            svc = services(active_only=False)
            st.dataframe(svc[["id","name","description","active"]], use_container_width=True, hide_index=True)
            with st.form("add_service"):
                name = st.text_input("New service name")
                desc = st.text_area("Service description")
                add = st.form_submit_button("Add service")
            if add:
                if name.strip() and desc.strip():
                    try:
                        with db() as con:
                            con.execute("INSERT INTO services(name,description,active) VALUES(?,?,1)", (name.strip(),desc.strip()))
                        st.success("Service added.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("A service with that name already exists.")
                else:
                    st.error("Enter a service name and description.")
            if not svc.empty:
                with st.form("service_toggle"):
                    sid = st.selectbox("Select service ID", svc["id"].tolist())
                    active = st.selectbox("Availability", ["Active", "Inactive"])
                    save = st.form_submit_button("Update service")
                if save:
                    with db() as con:
                        con.execute("UPDATE services SET active=? WHERE id=?", (1 if active=="Active" else 0, int(sid)))
                    st.success("Service availability updated.")
                    st.rerun()
        elif page == "Manage Appointment Schedules":
            st.title("Manage Appointment Schedules")
            if data.empty:
                st.info("No appointments have been requested.")
            else:
                st.dataframe(data[["Request ID","Resident","Service","Appointment Date","Time","Status"]].sort_values(["Appointment Date","Time"]), use_container_width=True, hide_index=True)
            st.caption(f"Default capacity: {SLOT_CAPACITY} appointments per time slot. Change SLOT_CAPACITY in app.py to adjust the prototype.")
        elif page == "Review & Verify Requests":
            st.title("Review Document Requests and Verify Requirements")
            if data.empty:
                st.info("No requests to review.")
            else:
                st.dataframe(data.drop(columns=["User ID"]), use_container_width=True, hide_index=True)
                rid = st.selectbox("Select request ID", data["Request ID"].tolist())
                row = data[data["Request ID"] == rid].iloc[0]
                st.write(f"**Resident:** {row['Resident']}  |  **Service:** {row['Service']}")
                st.write(f"**Purpose:** {row['Purpose']}")
                req_files = requirement_list(rid)
                st.subheader("Submitted requirements")
                if not req_files:
                    st.warning("No files uploaded for this request.")
                for f in req_files:
                    st.write(f"📎 {f['filename']}")
                    path = Path(f["stored_path"])
                    if path.exists():
                        st.download_button(f"Download {f['filename']}", path.read_bytes(), file_name=f["filename"], key=f"file_{f['id']}")
                with st.form("process_request"):
                    status = st.selectbox("Processing status", STATUSES, index=STATUSES.index(row["Status"]) if row["Status"] in STATUSES else 0)
                    note = st.text_area("Staff note / reason", value=row["Staff Note"] or "")
                    save = st.form_submit_button("Save status and notify resident")
                if save:
                    update_status(rid, int(row["User ID"]), status, note)
                    st.success("Request status updated and resident notified.")
                    st.rerun()
        else:
            st.title("Generate Reports")
            if data.empty:
                st.info("No data available for reports.")
            else:
                c1,c2,c3 = st.columns(3)
                c1.metric("Total Requests", len(data))
                c2.metric("Unique Residents", data["Username"].nunique())
                c3.metric("Services Requested", data["Service"].nunique())
                st.subheader("Requests by status")
                st.bar_chart(data["Status"].value_counts())
                st.subheader("Requests by service")
                st.bar_chart(data["Service"].value_counts())
                st.subheader("Detailed report")
                st.dataframe(data.drop(columns=["User ID"]), use_container_width=True, hide_index=True)
                st.download_button("Download full report (CSV)", data.drop(columns=["User ID"]).to_csv(index=False).encode(), "barangay_report.csv", "text/csv")
    else:
        st.error("Unknown account role. Contact the system administrator.")

st.sidebar.divider()
st.sidebar.caption("BSIS Capstone prototype • Test with fictional resident data only")
