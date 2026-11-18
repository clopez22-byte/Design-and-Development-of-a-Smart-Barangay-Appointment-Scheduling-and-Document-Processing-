
import streamlit as st
import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import date, datetime, timedelta
import pandas as pd

# =====================================================
# 1. PAGE CONFIGURATION AND DESIGN
# =====================================================

st.set_page_config(
    page_title="Smart Barangay System",
    page_icon="🏛️",
    layout="wide"
)

BASE = Path(__file__).parent
DB_PATH = BASE / "barangay.db"
UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');

.stApp {
    background: linear-gradient(135deg, #F4F7FB, #EAF2F6);
    font-family: 'DM Sans', sans-serif;
    color: #203247;
}

h1, h2, h3 {
    color: #142D4E !important;
    font-weight: 800 !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #142D4E, #23658A);
}

[data-testid="stSidebar"] * {
    color: white !important;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background: rgba(255,255,255,0.07);
    padding: 8px 10px;
    border-radius: 9px;
    margin: 3px 0;
}

.stButton > button,
.stFormSubmitButton > button,
.stDownloadButton > button {
    background: linear-gradient(100deg, #23658A, #2A9D8F);
    color: white;
    border: none;
    border-radius: 10px;
    min-height: 42px;
    font-weight: 700;
    transition: 0.2s;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover,
.stDownloadButton > button:hover {
    background: #142D4E;
    color: white;
    transform: translateY(-2px);
}

[data-testid="stMetric"] {
    background: white;
    border: 1px solid #E2EAF1;
    border-radius: 15px;
    padding: 18px;
    box-shadow: 0 5px 18px rgba(20,45,78,0.06);
}

[data-testid="stMetricValue"] {
    color: #23658A;
    font-weight: 800;
}

div[data-testid="stForm"] {
    background: white;
    padding: 22px;
    border: 1px solid #E2EAF1;
    border-radius: 15px;
}

.stTextInput input,
.stTextArea textarea,
.stDateInput input {
    border-radius: 9px;
}

[data-testid="stDataFrame"] {
    border-radius: 12px;
}

.hero {
    background: linear-gradient(115deg, #142D4E, #23658A, #2A9D8F);
    color: white;
    padding: 35px;
    border-radius: 20px;
    margin-bottom: 25px;
    box-shadow: 0 10px 25px rgba(20,45,78,0.15);
}

.hero h1, .hero p {
    color: white !important;
}

.hero p {
    font-size: 17px;
}

.portal-card {
    background: white;
    border: 1px solid #E2EAF1;
    border-radius: 18px;
    padding: 25px;
    min-height: 200px;
    box-shadow: 0 8px 22px rgba(20,45,78,0.06);
}

.portal-card h3 {
    margin-top: 10px;
}

.portal-card p {
    color: #718096;
}

div[data-testid="stAlert"] {
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# 2. DEFAULT SETTINGS
# =====================================================

DEFAULT_SERVICES = [
    (
        "Barangay Clearance",
        "Certificate for employment, school, or other lawful purposes."
    ),
    (
        "Certificate of Indigency",
        "Certification of indigency, subject to barangay verification."
    ),
    (
        "Certificate of Residency",
        "Certification that a resident lives in the barangay."
    ),
    (
        "Cedula / Community Tax Certificate",
        "Community tax-related service. Follow local issuing procedures."
    ),
    (
        "Barangay Business Clearance",
        "Barangay-level business clearance, subject to local requirements."
    )
]

TIME_SLOTS = [
    "8:00 AM - 9:00 AM",
    "9:00 AM - 10:00 AM",
    "10:00 AM - 11:00 AM",
    "1:00 PM - 2:00 PM",
    "2:00 PM - 3:00 PM",
    "3:00 PM - 4:00 PM"
]

SLOT_CAPACITY = 5

STATUSES = [
    "Pending",
    "Under Review",
    "Requirements Incomplete",
    "Approved",
    "Rejected",
    "Ready for Claiming",
    "Completed"
]


# =====================================================
# 3. DATABASE CONNECTION
# =====================================================

def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


# =====================================================
# 4. PASSWORD SECURITY
# =====================================================

def pw_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        150_000
    ).hex()

    return salt + "$" + key


def pw_check(password, stored):
    try:
        salt, key = stored.split("$", 1)

        calculated = pw_hash(password, salt).split("$", 1)[1]

        return secrets.compare_digest(calculated, key)

    except Exception:
        return False


# =====================================================
# 5. INITIALIZE DATABASE
# =====================================================

def init_db():

    with db() as con:

        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'resident',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS services(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            admin_note TEXT DEFAULT '',
            created_at TEXT NOT NULL,

            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(service_id) REFERENCES services(id)
        );

        CREATE TABLE IF NOT EXISTS requirements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,

            FOREIGN KEY(request_id) REFERENCES requests(id)
        );

        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            request_id INTEGER,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,

            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)

        # Create demo administrator if not existing
        admin = con.execute(
            "SELECT id FROM users WHERE username='admin'"
        ).fetchone()

        if not admin:
            con.execute("""
                INSERT INTO users(
                    full_name, username, password_hash,
                    role, created_at
                )
                VALUES(?,?,?,?,?)
            """, (
                "Barangay Administrator",
                "admin",
                pw_hash("admin12345"),
                "admin",
                datetime.now().isoformat(timespec="seconds")
            ))

        # Insert default services
        for name, desc in DEFAULT_SERVICES:
            con.execute("""
                INSERT OR IGNORE INTO services(
                    name, description, active
                )
                VALUES(?,?,1)
            """, (name, desc))


# =====================================================
# 6. USER FUNCTIONS
# =====================================================

def get_user(username):

    with db() as con:
        return con.execute(
            "SELECT * FROM users WHERE username=?",
            (username.strip().lower(),)
        ).fetchone()


def register(name, username, password):

    with db() as con:
        con.execute("""
            INSERT INTO users(
                full_name, username, password_hash,
                role, created_at
            )
            VALUES(?,?,?,?,?)
        """, (
            name.strip(),
            username.strip().lower(),
            pw_hash(password),
            "resident",
            datetime.now().isoformat(timespec="seconds")
        ))


# =====================================================
# 7. SERVICE FUNCTIONS
# =====================================================

def services(active_only=True):

    with db() as con:

        query = "SELECT * FROM services"

        if active_only:
            query += " WHERE active=1"

        query += " ORDER BY name"

        return pd.read_sql_query(query, con)


# =====================================================
# 8. APPOINTMENT FUNCTIONS
# =====================================================

def slots_left(day, slot):

    with db() as con:

        count = con.execute("""
            SELECT COUNT(*)
            FROM requests
            WHERE appointment_date=?
            AND time_slot=?
            AND status != 'Rejected'
        """, (str(day), slot)).fetchone()[0]

    return max(0, SLOT_CAPACITY - count)


def create_request(user_id, service_id, purpose, day, slot):

    with db() as con:

        count = con.execute("""
            SELECT COUNT(*)
            FROM requests
            WHERE appointment_date=?
            AND time_slot=?
            AND status != 'Rejected'
        """, (str(day), slot)).fetchone()[0]

        if count >= SLOT_CAPACITY:
            return None

        cursor = con.execute("""
            INSERT INTO requests(
                user_id, service_id, purpose,
                appointment_date, time_slot,
                status, created_at
            )
            VALUES(?,?,?,?,?,'Pending',?)
        """, (
            user_id,
            service_id,
            purpose.strip(),
            str(day),
            slot,
            datetime.now().isoformat(timespec="seconds")
        ))

        request_id = cursor.lastrowid

        con.execute("""
            INSERT INTO notifications(
                user_id, request_id, message, created_at
            )
            VALUES(?,?,?,?)
        """, (
            user_id,
            request_id,
            f"Your request #{request_id} was submitted and is pending review.",
            datetime.now().isoformat(timespec="seconds")
        ))

        return request_id


# =====================================================
# 9. REQUEST DATA FUNCTIONS
# =====================================================

def resident_data(user_id):

    with db() as con:

        return pd.read_sql_query("""
            SELECT
                r.id AS 'Request ID',
                s.name AS 'Service',
                r.purpose AS 'Purpose',
                r.appointment_date AS 'Appointment Date',
                r.time_slot AS 'Time',
                r.status AS 'Status',
                r.admin_note AS 'Staff Note'

            FROM requests r

            JOIN services s ON s.id=r.service_id

            WHERE r.user_id=?

            ORDER BY r.id DESC
        """, con, params=(user_id,))


def request_data():

    with db() as con:

        return pd.read_sql_query("""
            SELECT
                r.id AS 'Request ID',
                u.full_name AS 'Resident',
                u.username AS 'Username',
                s.name AS 'Service',
                r.purpose AS 'Purpose',
                r.appointment_date AS 'Appointment Date',
                r.time_slot AS 'Time',
                r.status AS 'Status',
                r.admin_note AS 'Staff Note',
                r.user_id AS 'User ID'

            FROM requests r

            JOIN users u ON u.id=r.user_id

            JOIN services s ON s.id=r.service_id

            ORDER BY r.appointment_date DESC, r.id DESC
        """, con)


# =====================================================
# 10. NOTIFICATION FUNCTIONS
# =====================================================

def notify(user_id, request_id, message):

    with db() as con:

        con.execute("""
            INSERT INTO notifications(
                user_id, request_id, message, created_at
            )
            VALUES(?,?,?,?)
        """, (
            user_id,
            request_id,
            message,
            datetime.now().isoformat(timespec="seconds")
        ))


def user_notifications(user_id):

    with db() as con:

        return pd.read_sql_query("""
            SELECT
                id AS 'ID',
                message AS 'Notification',
                created_at AS 'Date',
                is_read

            FROM notifications

            WHERE user_id=?

            ORDER BY id DESC
        """, con, params=(user_id,))


def mark_notifications_read(user_id):

    with db() as con:

        con.execute("""
            UPDATE notifications
            SET is_read=1
            WHERE user_id=?
        """, (user_id,))


def update_status(request_id, user_id, status, note):

    with db() as con:

        con.execute("""
            UPDATE requests
            SET status=?, admin_note=?
            WHERE id=?
        """, (status, note, int(request_id)))

    notify(
        user_id,
        int(request_id),
        f"Update for request #{request_id}: status is now '{status}'."
        + (f" Staff note: {note}" if note else "")
    )


# =====================================================
# 11. DOCUMENT REQUIREMENT FUNCTIONS
# =====================================================

def requirement_list(request_id):

    with db() as con:

        return con.execute("""
            SELECT *
            FROM requirements
            WHERE request_id=?
            ORDER BY id DESC
        """, (int(request_id),)).fetchall()


def add_requirement(request_id, uploaded):

    safe_name = Path(uploaded.name).name.replace(" ", "_")

    stored_name = (
        f"request_{request_id}_{secrets.token_hex(5)}_{safe_name}"
    )

    destination = UPLOAD_DIR / stored_name

    destination.write_bytes(uploaded.getbuffer())

    with db() as con:

        con.execute("""
            INSERT INTO requirements(
                request_id, filename, stored_path, uploaded_at
            )
            VALUES(?,?,?,?)
        """, (
            int(request_id),
            uploaded.name,
            str(destination),
            datetime.now().isoformat(timespec="seconds")
        ))


def active_user_requests(user_id):

    with db() as con:

        return con.execute("""
            SELECT id
            FROM requests
            WHERE user_id=?
            ORDER BY id DESC
        """, (user_id,)).fetchall()


# =====================================================
# 12. INITIALIZE APPLICATION
# =====================================================

init_db()

st.sidebar.title("🏛️ SMART BARANGAY")
st.sidebar.caption("Your Community Service Portal")


# =====================================================
# 13. LOGIN AND PORTAL SELECTION
# =====================================================

if "user_id" not in st.session_state:

    st.markdown("""
    <div class="hero">
        <h1>🏛️ Smart Barangay Portal</h1>
        <p>
        Your convenient online access to barangay appointments,
        certificates, and document requests.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if "portal_choice" not in st.session_state:
        st.session_state.portal_choice = "Home"

    # ---------------------------------------------
    # HOME PORTAL SELECTION
    # ---------------------------------------------

    if st.session_state.portal_choice == "Home":

        st.subheader("Welcome! Choose your portal.")

        col1, col2 = st.columns(2, gap="large")

        with col1:

            st.markdown("""
            <div class="portal-card">
                <h2>👤</h2>
                <h3>Resident Portal</h3>
                <p>
                Register, book appointments, request barangay
                documents, upload requirements, and track requests.
                </p>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                "Continue as Resident →",
                use_container_width=True
            ):

                st.session_state.portal_choice = "Resident"
                st.rerun()

        with col2:

            st.markdown("""
            <div class="portal-card">
                <h2>🛡️</h2>
                <h3>Admin / Staff Portal</h3>
                <p>
                Manage barangay services, review requests,
                verify documents, and generate reports.
                </p>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                "Continue as Admin / Staff →",
                use_container_width=True
            ):

                st.session_state.portal_choice = "Admin"
                st.rerun()

        st.info(
            "Please choose the appropriate portal to continue."
        )

    # ---------------------------------------------
    # RESIDENT PORTAL
    # ---------------------------------------------

    elif st.session_state.portal_choice == "Resident":

        if st.button("← Back to portal selection"):

            st.session_state.portal_choice = "Home"
            st.rerun()

        st.subheader("👤 Resident Portal")

        st.write(
            "Log in to your account or register as a new resident."
        )

        login_tab, register_tab = st.tabs([
            "Resident Login",
            "Create Account"
        ])

        with login_tab:

            with st.form("resident_login"):

                username = st.text_input("Username")

                password = st.text_input(
                    "Password",
                    type="password"
                )

                submit = st.form_submit_button(
                    "Login to Resident Portal",
                    use_container_width=True
                )

            if submit:

                user = get_user(username)

                if (
                    user
                    and user["role"] == "resident"
                    and pw_check(password, user["password_hash"])
                ):

                    st.session_state.update(
                        user_id=user["id"],
                        username=user["username"],
                        full_name=user["full_name"],
                        role=user["role"]
                    )

                    st.rerun()

                else:

                    st.error(
                        "Invalid resident username or password."
                    )

        with register_tab:

            with st.form("resident_register"):

                name = st.text_input("Full Name")

                new_username = st.text_input(
                    "Create Username"
                )

                password = st.text_input(
                    "Create Password",
                    type="password"
                )

                confirm = st.text_input(
                    "Confirm Password",
                    type="password"
                )

                submit = st.form_submit_button(
                    "Create Resident Account",
                    use_container_width=True
                )

            if submit:

                if not name.strip() or not new_username.strip():

                    st.error("Please complete all fields.")

                elif len(password) < 8:

                    st.error(
                        "Password must contain at least 8 characters."
                    )

                elif password != confirm:

                    st.error("Passwords do not match.")

                else:

                    try:

                        register(name, new_username, password)

                        st.success(
                            "Account created successfully! You can now log in."
                        )

                    except sqlite3.IntegrityError:

                        st.error(
                            "That username is already in use."
                        )

    # ---------------------------------------------
    # ADMIN PORTAL
    # ---------------------------------------------

    elif st.session_state.portal_choice == "Admin":

        if st.button("← Back to portal selection"):

            st.session_state.portal_choice = "Home"
            st.rerun()

        st.subheader("🛡️ Administrator / Staff Portal")

        st.caption(
            "Authorized barangay personnel only."
        )

        with st.form("admin_login"):

            username = st.text_input("Admin Username")

            password = st.text_input(
                "Admin Password",
                type="password"
            )

            submit = st.form_submit_button(
                "Login to Admin Portal",
                use_container_width=True
            )

        if submit:

            user = get_user(username)

            if (
                user
                and user["role"] == "admin"
                and pw_check(password, user["password_hash"])
            ):

                st.session_state.update(
                    user_id=user["id"],
                    username=user["username"],
                    full_name=user["full_name"],
                    role=user["role"]
                )

                st.rerun()

            else:

                st.error(
                    "Invalid administrator username or password."
                )

        st.info(
            "Demo admin account: admin / admin12345. "
            "Change this password before deployment."
        )


# =====================================================
# 14. LOGGED-IN USER AREA
# =====================================================

else:

    st.sidebar.divider()

    st.sidebar.write(
        f"**{st.session_state.full_name}**"
    )

    st.sidebar.caption(
        st.session_state.role.title()
    )

    if st.sidebar.button("Log out"):

        for key in [
            "user_id",
            "username",
            "full_name",
            "role"
        ]:

            st.session_state.pop(key, None)

        st.session_state.portal_choice = "Home"

        st.rerun()

    # =================================================
    # 15. RESIDENT DASHBOARD
    # =================================================

    if st.session_state.role == "resident":

        page = st.sidebar.radio(
            "RESIDENT MENU",
            [
                "Dashboard",
                "Available Services",
                "Book Appointment / Request Document",
                "Upload Requirements",
                "Track Requests",
                "Notifications",
                "Appointment History"
            ]
        )

        uid = st.session_state.user_id

        mine = resident_data(uid)

        # ---------------------------------------------
        # DASHBOARD
        # ---------------------------------------------

        if page == "Dashboard":

            st.title("🏠 Resident Dashboard")

            st.subheader(
                f"Welcome, {st.session_state.full_name}!"
            )

            st.write(
                "Manage your barangay appointments and document requests here."
            )

            total = len(mine)

            pending = (
                int((mine["Status"] == "Pending").sum())
                if not mine.empty else 0
            )

            approved = (
                int(mine["Status"].isin([
                    "Approved",
                    "Ready for Claiming",
                    "Completed"
                ]).sum())
                if not mine.empty else 0
            )

            col1, col2, col3 = st.columns(3)

            col1.metric("Total Requests", total)
            col2.metric("Pending Requests", pending)
            col3.metric("Approved Requests", approved)

            st.divider()

            st.subheader("📋 Recent Requests")

            if mine.empty:

                st.info(
                    "You have no requests yet. Start by choosing a service."
                )

            else:

                st.dataframe(
                    mine.head(5),
                    use_container_width=True,
                    hide_index=True
                )

        # ---------------------------------------------
        # AVAILABLE SERVICES
        # ---------------------------------------------

        elif page == "Available Services":

            st.title("📄 Available Barangay Services")

            svc = services()

            if svc.empty:

                st.info(
                    "No services are currently available."
                )

            else:

                for _, row in svc.iterrows():

                    with st.container(border=True):

                        st.subheader(
                            f"📌 {row['name']}"
                        )

                        st.write(row["description"])

        # ---------------------------------------------
        # BOOK APPOINTMENT
        # ---------------------------------------------

        elif page == "Book Appointment / Request Document":

            st.title("📅 Book Appointment")

            st.write(
                "Select a barangay service and choose your appointment schedule."
            )

            svc = services()

            if svc.empty:

                st.warning(
                    "There are no active services at the moment."
                )

            else:

                with st.form("new_request"):

                    chosen = st.selectbox(
                        "Select Barangay Service",
                        svc["name"].tolist()
                    )

                    purpose = st.text_area(
                        "Purpose of Request",
                        placeholder="Explain why you need this document..."
                    )

                    first_day = date.today() + timedelta(days=1)

                    appointment_day = st.date_input(
                        "Appointment Date",
                        value=first_day,
                        min_value=first_day,
                        max_value=date.today() + timedelta(days=60)
                    )

                    slot = st.selectbox(
                        "Appointment Time",
                        TIME_SLOTS
                    )

                    remaining = slots_left(
                        appointment_day,
                        slot
                    )

                    st.caption(
                        f"Available slots: {remaining} / {SLOT_CAPACITY}"
                    )

                    submit = st.form_submit_button(
                        "Submit Appointment Request",
                        use_container_width=True
                    )

                if submit:

                    if not purpose.strip():

                        st.error(
                            "Please provide the purpose of your request."
                        )

                    else:

                        service_id = int(
                            svc.loc[
                                svc["name"] == chosen,
                                "id"
                            ].iloc[0]
                        )

                        request_id = create_request(
                            uid,
                            service_id,
                            purpose,
                            appointment_day,
                            slot
                        )

                        if request_id:

                            st.success(
                                f"Your request was submitted! "
                                f"Request ID: #{request_id}"
                            )

                            st.rerun()

                        else:

                            st.error(
                                "That appointment slot is full. "
                                "Please choose another schedule."
                            )

        # ---------------------------------------------
        # UPLOAD REQUIREMENTS
        # ---------------------------------------------

        elif page == "Upload Requirements":

            st.title("📎 Upload Supporting Requirements")

            st.caption(
                "Allowed files: PDF, PNG, JPG, JPEG. "
                "Maximum size: 10 MB."
            )

            requests = active_user_requests(uid)

            if not requests:

                st.info(
                    "Please submit a document request first."
                )

            else:

                request_ids = [
                    r["id"] for r in requests
                ]

                rid = st.selectbox(
                    "Select Your Request",
                    request_ids,
                    format_func=lambda x: f"Request #{x}"
                )

                existing = requirement_list(rid)

                st.subheader("Previously Uploaded Files")

                if existing:

                    for file in existing:

                        st.write(
                            f"📄 {file['filename']} "
                            f"— {file['uploaded_at']}"
                        )

                else:

                    st.info("No files uploaded yet.")

                uploaded = st.file_uploader(
                    "Choose Requirement File",
                    type=["pdf", "png", "jpg", "jpeg"]
                )

                if st.button(
                    "Upload File",
                    disabled=uploaded is None
                ):

                    if uploaded.size > 10 * 1024 * 1024:

                        st.error(
                            "File is larger than 10 MB."
                        )

                    else:

                        add_requirement(rid, uploaded)

                        st.success(
                            "Requirement uploaded successfully!"
                        )

                        st.rerun()

        # ---------------------------------------------
        # TRACK REQUESTS
        # ---------------------------------------------

        elif page == "Track Requests":

            st.title("🔍 Track Request Status")

            if mine.empty:

                st.info(
                    "You have no requests to track."
                )

            else:

                st.dataframe(
                    mine[[
                        "Request ID",
                        "Service",
                        "Appointment Date",
                        "Time",
                        "Status",
                        "Staff Note"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )

                rid = st.selectbox(
                    "View Uploaded Requirements",
                    mine["Request ID"].tolist()
                )

                st.subheader(
                    f"Requirements for Request #{rid}"
                )

                files = requirement_list(rid)

                if files:

                    for file in files:

                        st.write(
                            f"📎 {file['filename']} "
                            f"— {file['uploaded_at']}"
                        )

                else:

                    st.info(
                        "No requirements uploaded for this request."
                    )

        # ---------------------------------------------
        # NOTIFICATIONS
        # ---------------------------------------------

        elif page == "Notifications":

            st.title("🔔 Notifications")

            notes = user_notifications(uid)

            unread = (
                int((notes["is_read"] == 0).sum())
                if not notes.empty else 0
            )

            st.metric(
                "Unread Notifications",
                unread
            )

            if not notes.empty:

                st.dataframe(
                    notes.drop(columns=["is_read"]),
                    use_container_width=True,
                    hide_index=True
                )

                if unread > 0:

                    if st.button("Mark All as Read"):

                        mark_notifications_read(uid)

                        st.success(
                            "Notifications marked as read."
                        )

                        st.rerun()

            else:

                st.info("You have no notifications yet.")

        # ---------------------------------------------
        # APPOINTMENT HISTORY
        # ---------------------------------------------

        elif page == "Appointment History":

            st.title("📚 Appointment History")

            if mine.empty:

                st.info(
                    "You have no appointment history yet."
                )

            else:

                st.dataframe(
                    mine[[
                        "Request ID",
                        "Service",
                        "Appointment Date",
                        "Time",
                        "Status"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )

                st.download_button(
                    "⬇️ Download Appointment History",
                    mine.to_csv(index=False).encode("utf-8"),
                    "appointment_history.csv",
                    "text/csv"
                )

    # =================================================
    # 16. ADMINISTRATOR / STAFF DASHBOARD
    # =================================================

    elif st.session_state.role == "admin":

        page = st.sidebar.radio(
            "ADMIN / STAFF MENU",
            [
                "Admin Dashboard",
                "Manage Services",
                "Manage Appointment Schedules",
                "Review & Verify Requests",
                "Generate Reports"
            ]
        )

        data = request_data()

        # ---------------------------------------------
        # ADMIN DASHBOARD
        # ---------------------------------------------

        if page == "Admin Dashboard":

            st.title("🛡️ Administrator Dashboard")

            st.subheader(
                f"Welcome, {st.session_state.full_name}!"
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Total Requests",
                len(data)
            )

            col2.metric(
                "Pending",
                int((data["Status"] == "Pending").sum())
                if not data.empty else 0
            )

            col3.metric(
                "Under Review",
                int((data["Status"] == "Under Review").sum())
                if not data.empty else 0
            )

            col4.metric(
                "Completed",
                int((data["Status"] == "Completed").sum())
                if not data.empty else 0
            )

            st.divider()

            st.subheader("📋 Latest Resident Requests")

            if data.empty:

                st.info(
                    "There are currently no resident requests."
                )

            else:

                st.dataframe(
                    data.drop(columns=["User ID"]).head(10),
                    use_container_width=True,
                    hide_index=True
                )

        # ---------------------------------------------
        # MANAGE SERVICES
        # ---------------------------------------------

        elif page == "Manage Services":

            st.title("⚙️ Manage Barangay Services")

            svc = services(active_only=False)

            st.subheader("Existing Services")

            st.dataframe(
                svc[["id", "name", "description", "active"]],
                use_container_width=True,
                hide_index=True
            )

            st.divider()

            st.subheader("➕ Add New Service")

            with st.form("add_service"):

                name = st.text_input(
                    "Service Name"
                )

                description = st.text_area(
                    "Service Description"
                )

                add = st.form_submit_button(
                    "Add Service",
                    use_container_width=True
                )

            if add:

                if name.strip() and description.strip():

                    try:

                        with db() as con:

                            con.execute("""
                                INSERT INTO services(
                                    name, description, active
                                )
                                VALUES(?,?,1)
                            """, (
                                name.strip(),
                                description.strip()
                            ))

                        st.success(
                            "New service added successfully!"
                        )

                        st.rerun()

                    except sqlite3.IntegrityError:

                        st.error(
                            "A service with that name already exists."
                        )

                else:

                    st.error(
                        "Please enter a service name and description."
                    )

            st.divider()

            st.subheader("Update Service Availability")

            if not svc.empty:

                with st.form("service_toggle"):

                    service_id = st.selectbox(
                        "Select Service ID",
                        svc["id"].tolist()
                    )

                    availability = st.selectbox(
                        "Availability",
                        ["Active", "Inactive"]
                    )

                    save = st.form_submit_button(
                        "Update Availability"
                    )

                if save:

                    with db() as con:

                        con.execute("""
                            UPDATE services
                            SET active=?
                            WHERE id=?
                        """, (
                            1 if availability == "Active" else 0,
                            int(service_id)
                        ))

                    st.success(
                        "Service availability updated."
                    )

                    st.rerun()

        # ---------------------------------------------
        # MANAGE APPOINTMENT SCHEDULES
        # ---------------------------------------------

        elif page == "Manage Appointment Schedules":

            st.title("📅 Manage Appointment Schedules")

            if data.empty:

                st.info(
                    "No appointments have been requested."
                )

            else:

                st.dataframe(
                    data[[
                        "Request ID",
                        "Resident",
                        "Service",
                        "Appointment Date",
                        "Time",
                        "Status"
                    ]].sort_values([
                        "Appointment Date",
                        "Time"
                    ]),
                    use_container_width=True,
                    hide_index=True
                )

            st.caption(
                f"Default capacity: {SLOT_CAPACITY} appointments "
                "per time slot."
            )

        # ---------------------------------------------
        # REVIEW AND VERIFY REQUESTS
        # ---------------------------------------------

        elif page == "Review & Verify Requests":

            st.title("📋 Review and Verify Requests")

            if data.empty:

                st.info(
                    "There are no requests to review."
                )

            else:

                st.dataframe(
                    data.drop(columns=["User ID"]),
                    use_container_width=True,
                    hide_index=True
                )

                rid = st.selectbox(
                    "Select Request ID",
                    data["Request ID"].tolist()
                )

                row = data[
                    data["Request ID"] == rid
                ].iloc[0]

                st.divider()

                st.subheader(
                    f"Request #{rid}"
                )

                st.write(
                    f"**Resident:** {row['Resident']}"
                )

                st.write(
                    f"**Service:** {row['Service']}"
                )

                st.write(
                    f"**Purpose:** {row['Purpose']}"
                )

                st.write(
                    f"**Appointment:** "
                    f"{row['Appointment Date']} — {row['Time']}"
                )

                st.divider()

                st.subheader("📎 Submitted Requirements")

                files = requirement_list(rid)

                if not files:

                    st.warning(
                        "No files uploaded for this request."
                    )

                for file in files:

                    st.write(
                        f"📄 {file['filename']}"
                    )

                    path = Path(file["stored_path"])

                    if path.exists():

                        st.download_button(
                            f"Download {file['filename']}",
                            path.read_bytes(),
                            file_name=file["filename"],
                            key=f"file_{file['id']}"
                        )

                st.divider()

                st.subheader("Update Request Status")

                with st.form("process_request"):

                    current_status = (
                        STATUSES.index(row["Status"])
                        if row["Status"] in STATUSES else 0
                    )

                    status = st.selectbox(
                        "Processing Status",
                        STATUSES,
                        index=current_status
                    )

                    note = st.text_area(
                        "Staff Note / Reason",
                        value=row["Staff Note"] or ""
                    )

                    save = st.form_submit_button(
                        "Save Status and Notify Resident",
                        use_container_width=True
                    )

                if save:

                    update_status(
                        rid,
                        int(row["User ID"]),
                        status,
                        note
                    )

                    st.success(
                        "Request status updated and resident notified."
                    )

                    st.rerun()

        # ---------------------------------------------
        # GENERATE REPORTS
        # ---------------------------------------------

        elif page == "Generate Reports":

            st.title("📊 Generate Reports")

            if data.empty:

                st.info(
                    "No data available for reports."
                )

            else:

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Total Requests",
                    len(data)
                )

                col2.metric(
                    "Unique Residents",
                    data["Username"].nunique()
                )

                col3.metric(
                    "Services Requested",
                    data["Service"].nunique()
                )

                st.divider()

                st.subheader("Requests by Status")

                status_counts = data["Status"].value_counts()

                st.bar_chart(status_counts)

                st.divider()

                st.subheader("Requests by Service")

                service_counts = data["Service"].value_counts()

                st.bar_chart(service_counts)

                st.divider()

                st.subheader("Detailed Report")

                st.dataframe(
                    data.drop(columns=["User ID"]),
                    use_container_width=True,
                    hide_index=True
                )

                st.download_button(
                    "⬇️ Download Full Report (CSV)",
                    data.drop(columns=["User ID"])
                    .to_csv(index=False)
                    .encode("utf-8"),
                    "barangay_report.csv",
                    "text/csv"
                )

    else:

        st.error(
            "Unknown account role. Contact the system administrator."
        )


# =====================================================
# 17. SIDEBAR FOOTER
# =====================================================

st.sidebar.divider()

st.sidebar.caption(
    "🏛️ Smart Barangay System"
)

st.sidebar.caption(
    "BSIS Capstone Project Prototype"
)

st.sidebar.caption(
    "Use fictional resident information while testing."
)
