import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
from io import BytesIO
from fpdf import FPDF

# -----------------------------
# Config
# -----------------------------
st.set_page_config(
    page_title="Spark Driver Mileage & Expense Tracker",
    page_icon="🚗",
    layout="centered"
)

IRS_RATE_PER_MILE = 0.725
DB_NAME = "spark_tracker.db"

APP_USERNAME = "driver"
APP_PASSWORD = "spark123"  # ← change for security


# -----------------------------
# Database
# -----------------------------
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_date TEXT NOT NULL,
            start_odometer REAL,
            end_odometer REAL,
            miles REAL NOT NULL,
            notes TEXT,
            odometer_image BLOB,
            created_at TEXT NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            receipt_image BLOB,
            created_at TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


def insert_trip(trip_date, start_odometer, end_odometer, miles, notes, odometer_image_bytes):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO trips (trip_date, start_odometer, end_odometer, miles, notes, odometer_image, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        trip_date, start_odometer, end_odometer, miles, notes,
        odometer_image_bytes, datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def insert_expense(expense_date, category, description, amount, receipt_image_bytes):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expenses (expense_date, category, description, amount, receipt_image, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        expense_date, category, description, amount,
        receipt_image_bytes, datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def load_trips_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM trips ORDER BY trip_date DESC, id DESC", conn)
    conn.close()
    return df


def load_expenses_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC", conn)
    conn.close()
    return df


# -----------------------------
# PDF
# -----------------------------
class IRSReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Spark Driver IRS Mileage & Expense Report", ln=True, align="C")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")


def generate_irs_pdf(trips_df, expenses_df, start_date, end_date):
    pdf = IRSReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Reporting period: {start_date} to {end_date}", ln=True)

    total_miles = trips_df["miles"].sum() if not trips_df.empty else 0
    total_deduction = total_miles * IRS_RATE_PER_MILE
    total_expenses = expenses_df["amount"].sum() if not expenses_df.empty else 0

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"Total miles: {total_miles:.2f}", ln=True)
    pdf.cell(0, 6, f"IRS deduction (${IRS_RATE_PER_MILE}/mile): ${total_deduction:,.2f}", ln=True)
    pdf.cell(0, 6, f"Total expenses: ${total_expenses:,.2f}", ln=True)
    pdf.ln(4)

    # Trips table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Trip Log", ln=True)
    pdf.set_font("Helvetica", "", 9)

    if trips_df.empty:
        pdf.cell(0, 6, "No trips recorded.", ln=True)
    else:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 6, "Date", border=1)
        pdf.cell(25, 6, "Miles", border=1)
        pdf.cell(135, 6, "Notes", border=1, ln=True)

        pdf.set_font("Helvetica", "", 9)
        for _, row in trips_df.iterrows():
            pdf.cell(30, 6, str(row["trip_date"]), border=1)
            pdf.cell(25, 6, f'{row["miles"]:.2f}', border=1)
            pdf.cell(135, 6, (row["notes"] or "")[:70], border=1, ln=True)

    pdf.ln(6)

    # Expenses
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Expenses", ln=True)

    if expenses_df.empty:
        pdf.cell(0, 6, "No expenses recorded.", ln=True)
    else:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 6, "Date", border=1)
        pdf.cell(40, 6, "Category", border=1)
        pdf.cell(25, 6, "Amount", border=1)
        pdf.cell(95, 6, "Description", border=1, ln=True)

        pdf.set_font("Helvetica", "", 9)
        for _, row in expenses_df.iterrows():
            pdf.cell(30, 6, str(row["expense_date"]), border=1)
            pdf.cell(40, 6, row["category"], border=1)
            pdf.cell(25, 6, f'${row["amount"]:.2f}', border=1)
            pdf.cell(95, 6, (row["description"] or "")[:70], border=1, ln=True)

    return BytesIO(pdf.output(dest="S").encode("latin-1"))


# -----------------------------
# Login
# -----------------------------
def show_login():
    st.title("🚗 Spark Driver Tracker - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == APP_USERNAME and password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Incorrect username or password.")


# -----------------------------
# Dashboard
# -----------------------------
def show_dashboard():
    st.title("🚗 Dashboard")

    trips = load_trips_df()
    expenses = load_expenses_df()

    total_miles = trips["miles"].sum() if not trips.empty else 0
    deduction = total_miles * IRS_RATE_PER_MILE
    total_expenses = expenses["amount"].sum() if not expenses.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Miles", f"{total_miles:.1f}")
    c2.metric("IRS Deduction", f"${deduction:,.2f}")
    c3.metric("Expenses", f"${total_expenses:,.2f}")

    st.subheader("Recent Trips")
    if trips.empty:
        st.info("No trips logged yet.")
    else:
        st.dataframe(trips[["trip_date", "miles", "notes"]].head(20))

    st.subheader("Recent Expenses")
    if expenses.empty:
        st.info("No expenses logged yet.")
    else:
        st.dataframe(expenses[["expense_date", "category", "amount"]].head(20))


# -----------------------------
# Log Trip
# -----------------------------
def show_log_trip():
    st.header("📝 Log Trip")

    trip_date = st.date_input("Trip Date", value=date.today())
    start = st.number_input("Start odometer (optional)", value=0.0)
    end = st.number_input("End odometer (optional)", value=0.0)
    miles = st.number_input("Miles (or leave 0 to auto calc)", value=0.0)
    notes = st.text_area("Notes")
    img = st.file_uploader("Odometer Photo", type=["png", "jpg", "jpeg"])

    if st.button("Save Trip"):
        if miles == 0 and end > start:
            miles = end - start
        elif miles == 0:
            st.error("Enter miles OR valid odometer readings.")
            return

        img_bytes = img.read() if img else None

        insert_trip(
            trip_date.isoformat(),
            start if start > 0 else None,
            end if end > 0 else None,
            miles,
            notes,
            img_bytes
        )

        st.success(f"Saved trip: {miles:.2f} miles")


# -----------------------------
# Log Expense
# -----------------------------
def show_log_expense():
    st.header("💸 Log Expense")

    expense_date = st.date_input("Expense Date", value=date.today())
    category = st.selectbox("Category", ["Gas", "Maintenance", "Parking/Tolls",
                                         "Car Wash", "Supplies", "Phone/Internet", "Other"])
    amount = st.number_input("Amount", value=0.0)
    desc = st.text_area("Description")
    receipt = st.file_uploader("Receipt", type=["png", "jpg", "jpeg"])

    if st.button("Save Expense"):
        if amount <= 0:
            st.error("Enter valid amount.")
            return

        rec = receipt.read() if receipt else None

        insert_expense(expense_date.isoformat(), category, desc, amount, rec)
        st.success("Expense Saved!")


# -----------------------------
# Reports
# -----------------------------
def get_quick_range(name):
    today = date.today()
    if name == "This Week (Mon-Sun)":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif name == "This Month":
        start = today.replace(day=1)
        end = date(today.year, today.month, 28) + timedelta(days=4)
        end = end.replace(day=1) - timedelta(days=1)
    elif name == "This Year":
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
    else:
        start = end = today
    return start, end


def show_reports():
    st.header("📊 Reports")

    trips = load_trips_df()
    expenses = load_expenses_df()

    if trips.empty and expenses.empty:
        st.info("No data yet.")
        return

    quick = st.selectbox("Range", ["Custom", "This Week (Mon-Sun)", "This Month", "This Year"], index=3)

    if quick == "Custom":
        start = st.date_input("Start", value=date.today().replace(month=1, day=1))
        end = st.date_input("End", value=date.today())
    else:
        start, end = get_quick_range(quick)
        st.write(f"From **{start}** to **{end}**")

    t = trips[(trips.trip_date >= start.isoformat()) & (trips.trip_date <= end.isoformat())] if not trips.empty else trips
    e = expenses[(expenses.expense_date >= start.isoformat()) & (expenses.expense_date <= end.isoformat())] if not expenses.empty else expenses

    st.metric("Miles", t["miles"].sum() if not t.empty else 0)
    st.metric("Expenses", e["amount"].sum() if not e.empty else 0)

    if st.button("Generate IRS PDF"):
        pdf = generate_irs_pdf(t, e, start, end)
        st.download_button("Download PDF", data=pdf, file_name="irs_report.pdf", mime="application/pdf")


# -----------------------------
# Settings
# -----------------------------
def show_settings():
    st.header("⚙️ Settings & Help")
    st.write("Single-user app. Data stored locally in SQLite DB.")
    st.write("To secure login, change username/password in code.")
    st.write("Add to home screen for mobile app feel.")


# -----------------------------
# Main
# -----------------------------
def main():
    init_db()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        show_login()
        return

    menu = st.sidebar.radio("Navigation", [
        "Dashboard",
        "Log Trip",
        "Log Expense",
        "Reports & Export",
        "Settings"
    ])

    if menu == "Dashboard":
        show_dashboard()
    elif menu == "Log Trip":
        show_log_trip()
    elif menu == "Log Expense":
        show_log_expense()
    elif menu == "Reports & Export":
        show_reports()
    elif menu == "Settings":
        show_settings()

    if st.sidebar.button("Log Out"):
        st.session_state.logged_in = False
        st.rerun()


if __name__ == "__main__":
    main()
