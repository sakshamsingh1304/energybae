"""
excel_handler.py — Excel template injection for Energybae Solar Proposals.

Loads the bundled MSEDCL analysis template, clears old data,
injects fresh extracted data, and preserves all formulas.
"""

import os
import openpyxl
from io import BytesIO

# Bundled template path (shipped with the app)
TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "Copy of Pranay HOME E-Bill Analysis.xlsx"
)

# Cell mapping for up to 2 consumers
CONSUMER_SLOTS = [
    {
        "name": "D1",
        "number": "D2",
        "fixed": "D3",
        "load": "D4",
        "conn": "D5",
        "units_col": "D",
        "bill_cell": "E20",
    },
    {
        "name": "H1",
        "number": "H2",
        "fixed": "H3",
        "load": "H4",
        "conn": "H5",
        "units_col": "H",
        "bill_cell": "I20",
    },
]

UNITS_ROW_START = 9  # Monthly consumption starts at row 9
UNITS_ROW_END = 20   # Up to 12 months (rows 9–20)


def inject_into_excel(consumers: list[dict]) -> BytesIO:
    """
    Load the bundled template, clear old data, inject fresh data,
    and return the Excel workbook as a BytesIO stream.

    The template contains formulas that calculate:
    - Average consumption (D22/H22)
    - Required kW capacity (D23/H23)
    - Number of solar panels (D24/H24)
    - Solar capacity (D25/H25)

    These formulas are PRESERVED — we only inject raw data cells.

    Args:
        consumers: List of cleaned consumer data dicts (max 2)

    Returns:
        BytesIO containing the populated .xlsx file
    """
    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    sheet = wb.active

    # ── Clear ALL input cells first ──
    for slot in CONSUMER_SLOTS:
        sheet[slot["name"]] = None
        sheet[slot["number"]] = None
        sheet[slot["fixed"]] = None
        sheet[slot["load"]] = None
        sheet[slot["conn"]] = None
        sheet[slot["bill_cell"]] = None
        col = slot["units_col"]
        for row in range(UNITS_ROW_START, UNITS_ROW_END + 1):
            sheet[f"{col}{row}"] = None

    # ── Inject extracted data ──
    for idx, data in enumerate(consumers[:2]):
        s = CONSUMER_SLOTS[idx]

        # Consumer name
        if data.get("consumer_name"):
            sheet[s["name"]] = data["consumer_name"]

        # Consumer number — store as integer if all digits, else as string
        if data.get("consumer_number"):
            num = str(data["consumer_number"]).strip()
            try:
                sheet[s["number"]] = int(num)
            except ValueError:
                sheet[s["number"]] = num

        # Fixed charges — default to 130 if not extracted
        if data.get("fixed_charges") is not None:
            try:
                sheet[s["fixed"]] = float(data["fixed_charges"])
            except (ValueError, TypeError):
                sheet[s["fixed"]] = 130
        else:
            sheet[s["fixed"]] = 130

        # Sanctioned load
        if data.get("sanctioned_load"):
            sheet[s["load"]] = data["sanctioned_load"]

        # Connection type
        if data.get("connection_type"):
            sheet[s["conn"]] = data["connection_type"]

        # Monthly consumption (up to 12 months)
        history = data.get("monthly_consumption", [])
        col = s["units_col"]
        for i, month_data in enumerate(history[:12]):
            row = UNITS_ROW_START + i
            units = month_data.get("units")
            if units is not None:
                try:
                    sheet[f"{col}{row}"] = int(units)
                except (ValueError, TypeError):
                    pass

        # Bill amount (latest month)
        if data.get("bill_amount") is not None:
            try:
                sheet[s["bill_cell"]] = float(data["bill_amount"])
            except (ValueError, TypeError):
                pass

    # ── Save to BytesIO ──
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
