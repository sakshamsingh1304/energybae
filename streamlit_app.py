import streamlit as st
import json
import base64
import openpyxl
from io import BytesIO
import os
from dotenv import load_dotenv
from groq import Groq

# Load API key from .env
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Bundled template path (shipped with the app)
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "Copy of Pranay HOME E-Bill Analysis.xlsx")

# Groq vision model
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ──────────────────────────────────────────────
# Page Config & Styling — matched to energybae.in
# ──────────────────────────────────────────────
st.set_page_config(page_title="EnergyBae — Solar Load Calculator", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

    /* ── Global ── */
    html, body, p, div, span, h1, h2, h3, h4, h5, h6, li, button, a { font-family: 'Poppins', sans-serif !important; }
    .block-container { padding-top: 2rem; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 40%, #388E3C 100%);
    }
    section[data-testid="stSidebar"] * { color: #fff !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2); }

    /* ── Header ── */
    .eb-header {
        display: flex; align-items: center; gap: 14px;
        margin-bottom: 4px;
    }
    .eb-logo {
        font-size: 2.2rem; font-weight: 800;
        color: #2E7D32; letter-spacing: -0.5px;
    }
    .eb-logo span { color: #F9A825; }
    .eb-subtitle {
        color: #666; font-size: 1rem; margin-bottom: 24px;
        font-weight: 400;
    }

    /* ── Step labels ── */
    .step-label {
        display: inline-block;
        background: #2E7D32; color: #fff;
        padding: 3px 12px; border-radius: 14px;
        font-size: 0.75rem; font-weight: 600;
        letter-spacing: 0.5px; margin-right: 6px;
    }

    /* ── Cards ── */
    .eb-card {
        background: #f8fdf8; border: 1px solid #C8E6C9;
        border-radius: 10px; padding: 16px 20px; margin: 8px 0;
    }

    /* ── Buttons ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2E7D32, #43A047) !important;
        border: none !important; font-weight: 600 !important;
        letter-spacing: 0.3px;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #1B5E20, #2E7D32) !important;
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #2E7D32, #43A047) !important;
        color: #fff !important; border: none !important;
        font-weight: 600 !important;
    }

    /* ── Metric styling ── */
    [data-testid="stMetricValue"] { color: #2E7D32 !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #555 !important; font-weight: 500 !important; }

    /* ── File Uploader ── */
    [data-testid="stFileUploader"] section {
        border: 2px dashed #2E7D32 !important;
        background-color: #f8fdf8 !important;
        border-radius: 12px;
    }
    [data-testid="stFileUploader"] button {
        background-color: #2E7D32 !important;
        color: white !important;
        border: none !important;
        padding: 6px 16px !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
    }

    /* ── Footer ── */
    .eb-footer {
        text-align: center; color: #999; font-size: 0.78rem;
        margin-top: 40px; padding: 16px 0;
        border-top: 1px solid #eee;
    }
    .eb-footer a { color: #2E7D32; text-decoration: none; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
st.markdown("""
<div class="eb-header">
    <div class="eb-logo">⚡ Energy<span>Bae</span></div>
</div>
<div class="eb-subtitle">Upload your electricity bill → AI extracts data → Download a ready-to-use Solar Proposal</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ EnergyBae")
    st.markdown("*Empowering People with*\n*Renewable Energy Solutions*")
    st.markdown("---")
    st.markdown("### How It Works")
    st.markdown("""
1. **Upload** your electricity bill
2. **Click** Generate Proposal
3. **Download** the filled Excel

*That's it — fully automated!*
    """)
    st.markdown("---")
    st.markdown("### Key Features")
    st.markdown("""
- ✅ AI-powered bill reading
- ✅ 12-month consumption history
- ✅ Solar formulas preserved
- ✅ One-click Excel download
    """)
    st.markdown("---")
    st.markdown("📧 freeenergy@energybae.in")
    st.markdown("[🌐 energybae.in](https://www.energybae.in)")

# ──────────────────────────────────────────────
# Extraction prompt
# ──────────────────────────────────────────────
EXTRACTION_PROMPT = """You are an expert data extraction agent for an Indian solar energy company.
Extract the following from this MSEDCL (Maharashtra State Electricity Distribution Co. Ltd) electricity bill.

Return a JSON object with EXACTLY these fields:
{
  "consumer_name": "Full name as printed on the bill",
  "consumer_number": "The consumer number (numeric string)",
  "connection_type": "e.g. 90/LT I Res 1-Phase - include tariff code",
  "sanctioned_load": "e.g. 3.30KW - include the unit",
  "fixed_charges": null,
  "bill_amount": <total bill amount for current month as a number>,
  "monthly_consumption": [
    {"month": "Feb 2025", "units": <number>},
    {"month": "Mar 2025", "units": <number>},
    ...up to 12 months, OLDEST first, NEWEST last
  ]
}

RULES:
- Monthly consumption is shown as a BAR CHART on the bill. Read ALL visible months and their unit values.
- Order: OLDEST first, NEWEST last.
- bill_amount: the primary payable amount. Look for the field labeled "देयक रक्कम" or "Amount Payable". Not the after-due amount.
- consumer_number: the field labeled "ग्राहक क्रमांक".
- sanctioned_load: the field labeled "मंजूर भार" or "Sanctioned Load". KEEP the unit (e.g. "3.30KW").
- connection_type: include the tariff code (e.g. "90/LT I Res 1-Phase"). Look for "दर संकेत" field.
- If a value cannot be read clearly, set it to null.
- Return ONLY valid JSON. No markdown fences, no explanation, no extra text."""

# ──────────────────────────────────────────────
# Groq Vision extraction
# ──────────────────────────────────────────────
def extract_with_groq(file_bytes, file_name):
    """Extract bill data using Groq Vision API (Llama 4 Scout)."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set. Add it to your .env file.")

    client = Groq(api_key=GROQ_API_KEY)

    ext = os.path.splitext(file_name)[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    mime_type = mime_map.get(ext, "image/jpeg")

    b64_image = base64.b64encode(file_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_image}"
                        },
                    },
                ],
            }
        ],
        temperature=0.1,
        max_completion_tokens=2048,
    )

    raw = response.choices[0].message.content
    json_str = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(json_str)

# ──────────────────────────────────────────────
# Excel injection
# ──────────────────────────────────────────────
CONSUMER_SLOTS = [
    {"name": "D1", "number": "D2", "fixed": "D3", "load": "D4",
     "conn": "D5", "units_col": "D", "bill_cell": "E20"},
    {"name": "H1", "number": "H2", "fixed": "H3", "load": "H4",
     "conn": "H5", "units_col": "H", "bill_cell": "I20"},
]
UNITS_ROW_START = 9

def inject_into_excel(consumers):
    """Load the bundled template, clear old data, inject fresh data, return BytesIO output."""
    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    sheet = wb.active

    # Clear ALL input cells first
    for slot in CONSUMER_SLOTS:
        sheet[slot["name"]] = None
        sheet[slot["number"]] = None
        sheet[slot["fixed"]] = None
        sheet[slot["load"]] = None
        sheet[slot["conn"]] = None
        sheet[slot["bill_cell"]] = None
        col = slot["units_col"]
        for row in range(UNITS_ROW_START, UNITS_ROW_START + 12):
            sheet[f"{col}{row}"] = None

    # Inject extracted data
    for idx, data in enumerate(consumers[:2]):
        s = CONSUMER_SLOTS[idx]

        if data.get("consumer_name"):
            sheet[s["name"]] = data["consumer_name"]
        if data.get("consumer_number"):
            num = data["consumer_number"]
            sheet[s["number"]] = int(num) if str(num).isdigit() else num
        if data.get("fixed_charges") is not None:
            sheet[s["fixed"]] = data["fixed_charges"]
        else:
            sheet[s["fixed"]] = 130
        if data.get("sanctioned_load"):
            sheet[s["load"]] = data["sanctioned_load"]
        if data.get("connection_type"):
            sheet[s["conn"]] = data["connection_type"]

        history = data.get("monthly_consumption", [])
        col = s["units_col"]
        for i, month_data in enumerate(history[:12]):
            row = UNITS_ROW_START + i
            units = month_data.get("units")
            if units is not None:
                sheet[f"{col}{row}"] = units

        if data.get("bill_amount") is not None:
            sheet[s["bill_cell"]] = data["bill_amount"]

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# ──────────────────────────────────────────────
# Main UI
# ──────────────────────────────────────────────
st.markdown('<span class="step-label">STEP 1</span> **Upload Electricity Bill(s)**', unsafe_allow_html=True)
st.caption("Upload 1 or 2 electricity bills (JPG / PNG). First bill → Consumer 1, second → Consumer 2.")

bill_files = st.file_uploader(
    "Upload Bill(s)",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if bill_files:
    cols = st.columns(len(bill_files[:2]))
    for i, bill in enumerate(bill_files[:2]):
        with cols[i]:
            st.markdown(f"**Bill {i+1}:** `{bill.name}`")
            st.image(bill, use_container_width=True)

st.markdown("---")

# Generate button
if st.button("⚡ Generate Solar Proposal", type="primary", use_container_width=True):
    if not bill_files:
        st.warning("Please upload at least one electricity bill.")
    elif not GROQ_API_KEY:
        st.error("🔑 API key not configured. Add `GROQ_API_KEY=your_key` to the `.env` file and restart.")
    else:
        consumers = []

        for i, bill in enumerate(bill_files[:2]):
            with st.spinner(f"Analyzing bill {i+1} of {len(bill_files[:2])} with AI..."):
                try:
                    data = extract_with_groq(bill.getvalue(), bill.name)
                    consumers.append(data)
                    st.success(f"Bill {i+1} extracted — **{data.get('consumer_name', 'Unknown')}**")
                except Exception as e:
                    st.error(f"Error processing bill {i+1}: {str(e)}")

        if consumers:
            # Show extracted data
            st.markdown('<span class="step-label">STEP 2</span> **Extracted Data**', unsafe_allow_html=True)

            for i, data in enumerate(consumers):
                with st.expander(f"Consumer {i+1}: {data.get('consumer_name', 'N/A')}", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Consumer No", data.get("consumer_number", "N/A"))
                    c2.metric("Connection", data.get("connection_type", "N/A"))
                    c3.metric("Load", data.get("sanctioned_load", "N/A"))
                    c4.metric("Bill Amount", f"₹{data.get('bill_amount', 'N/A')}")

                    history = data.get("monthly_consumption", [])
                    if history:
                        st.markdown(f"**Monthly Consumption** ({len(history)} months)")
                        st.dataframe(
                            [{"Month": m["month"], "Units (kWh)": m["units"]} for m in history],
                            use_container_width=True, hide_index=True,
                        )

            # Inject into Excel & offer download
            st.markdown('<span class="step-label">STEP 3</span> **Download Proposal**', unsafe_allow_html=True)

            with st.spinner("Populating Excel template..."):
                try:
                    result = inject_into_excel(consumers)
                    st.success("Solar proposal generated successfully! All formulas preserved.")
                    st.download_button(
                        label="⬇️ Download Solar Proposal (Excel)",
                        data=result,
                        file_name="Energybae_Customer_Proposal.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Error generating Excel: {str(e)}")

# Footer
st.markdown("""
<div class="eb-footer">
    <a href="https://www.energybae.in" target="_blank">EnergyBae</a> — Empowering People with Renewable Energy Solutions<br>
    Pune, Maharashtra, India &nbsp;|&nbsp; freeenergy@energybae.in
</div>
""", unsafe_allow_html=True)
