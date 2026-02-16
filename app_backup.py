# app.py
import os
import streamlit as st
import pandas as pd
import sqlite3
from io import StringIO
from datetime import date
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
import tempfile

# ----------------- Page Config -----------------
st.set_page_config(layout="wide")

# ----------------- Database Setup -----------------
db_path = "factory.db"
first_time = not os.path.exists(db_path)

conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

if first_time:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily (
        worker_id TEXT,
        name TEXT,
        role TEXT,
        work TEXT,
        category TEXT,
        target TEXT,
        achieved TEXT,
        entry_date TEXT
    )
    """)
    conn.commit()

# ----------------- PDF Styles -----------------
ORANGE = HexColor("#ffa14f")
LIGHT_ORANGE = HexColor("#fce2ca")

def generate_daily_report_pdf(report_date, conn):
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(tmp_file.name, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'title', fontSize=14, alignment=TA_CENTER, textColor=colors.black,
        leading=16, spaceAfter=10, spaceBefore=10
    )
    title = Paragraph("GOODWILL FABRICS PVT. LTD - TAILOR EFFICIENCY CHART - DP UNIT 2", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))

    subtitle = Paragraph(f"Daily Report - {report_date}", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 12))

    # Fetch workers
    workers = pd.read_sql(
        "SELECT DISTINCT worker_id, name FROM daily WHERE entry_date <= ? ORDER BY worker_id",
        conn, params=(str(report_date),)
    )

    for _, w in workers.iterrows():
        worker_id = w["worker_id"]
        df = pd.read_sql(
            """
            SELECT entry_date AS Date,
                   worker_id AS ID,
                   name AS Name,
                   role AS Role,
                   work AS Work,
                   category AS Category,
                   achieved AS Achieved
            FROM daily
            WHERE worker_id = ? AND entry_date <= ?
            ORDER BY entry_date DESC
            LIMIT 6
            """, conn, params=(worker_id, str(report_date))
        )

        if df.empty:
            continue

        df = df.fillna("")
        for col in ["ID", "Achieved"]:
            df[col] = df[col].apply(lambda x: str(int(float(x))) if str(x).replace('.', '', 1).isdigit() else str(x))
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d-%m-%Y')

        table_data = [df.columns.tolist()]
        for row in df.itertuples(index=False):
            table_data.append([Paragraph(str(cell), styles['Normal']) for cell in row])

        col_widths = [70, 50, 80, 60, 120, 120, 50]
        t = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), ORANGE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), LIGHT_ORANGE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOX', (0, 0), (-1, -1), 1, ORANGE),
            ('GRID', (0, 0), (-1, -1), 0.5, ORANGE),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    doc.build(elements)
    return tmp_file.name

# ----------------- Sidebar Navigation -----------------
st.sidebar.title("📊 Navigation")
page = st.sidebar.radio("Go to", ["Excel Data Entry", "Daily Report", "Edit Worker Details"])

# ================= EXCEL DATA ENTRY =================
if page == "Excel Data Entry":
    st.title("GOODWILL FABRICS PVT. LTD - TAILOR EFFICIENCY CHART - DP UNIT 2")
    st.header("Excel Data Entry")

    entry_date = st.date_input("Select Entry Date", value=date.today(), max_value=date.today())
    raw_data = st.text_area("Paste Excel data here (copy directly from Excel)", height=300)

    if st.button("💾 Save Data"):
        if raw_data.strip():
            df = pd.read_csv(StringIO(raw_data), sep="\t", header=None)
            df = df.iloc[:, :7]
            df.columns = ["S.NO", "worker_id", "name", "role", "work", "category", "achieved"]

            df["worker_id"] = df["worker_id"].astype(str).str.replace(".0", "", regex=False)
            df["target"] = ""
            df["entry_date"] = str(entry_date)

            df = df[["worker_id", "name", "role", "work", "category", "target", "achieved", "entry_date"]]
            df.to_sql("daily", conn, if_exists="append", index=False)

            st.success("✅ Data saved successfully")
        else:
            st.warning("Paste Excel data first")

# ================= DAILY REPORT =================
if page == "Daily Report":
    st.title("Daily Report")

    report_date = st.date_input("Select Report Date", value=date.today())
    search_id = st.text_input("🔎 Search by Worker ID", placeholder="Enter ID")

    if st.button("⬇️ Download PDF"):
        pdf_path = generate_daily_report_pdf(report_date, conn)
        with open(pdf_path, "rb") as f:
            st.download_button(
                "📄 Click to Download PDF",
                f,
                file_name=f"Daily_Report_{report_date}.pdf",
                mime="application/pdf"
            )

    if search_id.strip():
        workers = pd.read_sql(
            "SELECT DISTINCT worker_id, name FROM daily WHERE entry_date <= ? AND worker_id=? ORDER BY worker_id",
            conn, params=(str(report_date), search_id.strip())
        )
    else:
        workers = pd.read_sql(
            "SELECT DISTINCT worker_id, name FROM daily WHERE entry_date <= ? ORDER BY worker_id",
            conn, params=(str(report_date),)
        )

    if workers.empty:
        st.info("No records found")
    else:
        for _, w in workers.iterrows():
            worker_id = w["worker_id"]
            df = pd.read_sql(
                """
                SELECT entry_date AS Date, worker_id AS ID, name AS Name,
                       role AS Role, work AS Work, category AS Category,
                       target AS Target, achieved AS Achieved
                FROM daily
                WHERE worker_id=? AND entry_date<=?
                ORDER BY entry_date DESC
                LIMIT 6
                """, conn, params=(worker_id, str(report_date))
            )

            df = df.fillna("")
            for col in ["ID", "Achieved"]:
                df[col] = df[col].apply(lambda x: str(int(float(x))) if str(x).replace('.', '', 1).isdigit() else str(x))
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d-%m-%Y')

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown("---")

# ================= EDIT WORKER =================
if page == "Edit Worker Details":
    st.title("✏️ Edit Worker Details")
    search_id = st.text_input("Enter Worker ID to Edit")

    if st.button("🔍 Search Worker"):
        if search_id.strip():
            worker_data = pd.read_sql(
                "SELECT DISTINCT worker_id, name FROM daily WHERE worker_id=?",
                conn, params=(search_id.strip(),)
            )

            if worker_data.empty:
                st.error("❌ Worker ID not found")
            else:
                st.session_state["edit_worker"] = worker_data.iloc[0].to_dict()
                st.success("Worker found below 👇")

    if "edit_worker" in st.session_state:
        current_data = st.session_state["edit_worker"]
        new_id = st.text_input("Edit Worker ID", value=current_data["worker_id"])
        new_name = st.text_input("Edit Name", value=current_data["name"])
        confirm_update = st.checkbox("Confirm Update")

        if st.button("💾 Update Worker"):
            if confirm_update:
                cursor.execute(
                    "UPDATE daily SET worker_id=?, name=? WHERE worker_id=?",
                    (new_id.strip(), new_name.strip(), current_data["worker_id"])
                )
                conn.commit()
                st.success("✅ Worker details updated successfully")
                del st.session_state["edit_worker"]
            else:
                st.warning("Please confirm before updating")
