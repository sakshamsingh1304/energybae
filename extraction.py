"""
extraction.py — Groq Vision API extraction for MSEDCL electricity bills.

Uses a heavily fine-tuned trilingual prompt (Marathi, Hindi, English)
with two-pass self-validation for maximum accuracy.
"""

import json
import base64
import os
from groq import Groq

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ──────────────────────────────────────────────────────────────────────
# The extraction prompt — trilingual, field-by-field, with validation
# ──────────────────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are a highly precise data extraction agent specializing in Indian electricity bills, specifically MSEDCL (Maharashtra State Electricity Distribution Co. Ltd) bills.

Your job is to extract structured data from this bill image with PERFECT accuracy. The bill contains text in Marathi (मराठी), Hindi (हिंदी), and English. You MUST read ALL three languages.

═══════════════════════════════════════════════════════
STEP 1: LOCATE AND EXTRACT EACH FIELD
═══════════════════════════════════════════════════════

Extract the following fields. Look for THESE EXACT LABELS:

────────────────────────────────────────
FIELD 1: consumer_name (ग्राहकाचे नाव / Consumer Name)
────────────────────────────────────────
- Look for the label: "ग्राहकाचे नाव" or "Consumer Name"
- Extract the FULL name exactly as printed

────────────────────────────────────────
FIELD 2: consumer_number (ग्राहक क्रमांक / Consumer Number / Consumer No)
────────────────────────────────────────
- Find the label: "ग्राहक क्रमांक" or "Consumer No"
- The consumer number MUST be EXACTLY 12 digits long (e.g., 160233166917).
- WARNING: Right above "ग्राहक क्रमांक", there is usually a label "(GGN):" followed by a 15-digit number starting with zeros (e.g., 000003219975928). THIS IS THE WRONG NUMBER. DO NOT EXTRACT IT.
- If the number you are looking at starts with "0000" or is 15 digits long, YOU ARE LOOKING AT THE GGN. STOP and look below it for the 12-digit "ग्राहक क्रमांक".
- ONLY extract the 12-digit number.
- If you see spaces, remove them.

────────────────────────────────────────
FIELD 3: connection_type (दर संकेत / Tariff Category)
────────────────────────────────────────
- Look for the label: "दर संकेत" or "Tariff"
- e.g.: "90/LT I Res 1-Phase"

────────────────────────────────────────
FIELD 4: sanctioned_load (मंजूर भार / Sanctioned Load)
────────────────────────────────────────
- Look for the label: "मंजूर भार"
- e.g.: "3.30KW" or "1KW"

────────────────────────────────────────
FIELD 5: bill_amount (देयक रक्कम / Amount Payable)
────────────────────────────────────────
- Look for the label: "देयक रक्कम" or "Amount Payable"
- Return as a NUMBER.

────────────────────────────────────────
FIELD 6: fixed_charges (स्थिर आकार / Fixed Charges)
────────────────────────────────────────
- Look for "स्थिर आकार"
- Return as a number. If not found, return null.

────────────────────────────────────────
FIELD 7: monthly_consumption (मासिक वीज वापर / Monthly Consumption)
────────────────────────────────────────
- Look for a section labeled "मागील वापर" or "Previous Consumption" or a bar chart showing units per month
- READ EACH MONTH AND ITS UNIT VALUE VERY CAREFULLY
- MSEDCL usually provides a tabular format (text) of past months below or near the chart. PREFER TEXT NUMBERS OVER GUESSING FROM THE BAR CHART.
- CRITICAL: MSEDCL bills almost always show a history of 11 to 12 months. DO NOT stop after 3 months. Scan the entire chart or table horizontally and vertically. You MUST extract every single month you see.
- Order: OLDEST month first, NEWEST month last
- Each entry: {"month": "Mon YYYY", "units": <integer>}

═══════════════════════════════════════════════════════
STEP 2: CHAIN OF THOUGHT AND RETURN FORMAT
═══════════════════════════════════════════════════════

First, use a <thinking> block to explain what you see on the bill. Read out the values you found for each field and explain why you chose them. 
- For consumer_number, explicitly state the numbers you see and verify which one is 12 digits.
- For monthly_consumption, explicitly state the values you are reading from the table/chart.

Then, output the JSON block enclosed in ```json ... ```.

Example format:
<thinking>
1. consumer_name: Found "JOHN DOE" next to ग्राहकाचे नाव.
2. consumer_number: I see GGN 000003219975928 (15 digits, starts with 0000) and 160233166917 (12 digits) next to ग्राहक क्रमांक. I am ignoring the GGN and picking 160233166917.
3. monthly_consumption: I must find all 11-12 months from the past year. I see a table with values Jan: 100, Feb: 120, Mar: 110, Apr: 130... I will extract all of them.
</thinking>
```json
{
  "consumer_name": "JOHN DOE",
  "consumer_number": "439320095567",
  "connection_type": "90/LT I Res 1-Phase",
  "sanctioned_load": "3.30KW",
  "fixed_charges": 130,
  "bill_amount": 320.45,
  "monthly_consumption": [
    {"month": "Jan 2025", "units": 100},
    {"month": "Feb 2025", "units": 120}
  ]
}
```

ABSOLUTE RULES:
- Include the <thinking> block.
- Return ONLY valid JSON in the ```json block.
"""

import re

def extract_with_groq(file_bytes: bytes, file_name: str, api_key: str) -> dict:
    """
    Extract bill data from an image using Groq Vision API (Llama 4 Scout).

    Args:
        file_bytes: Raw image bytes
        file_name: Original filename (used to determine MIME type)
        api_key: Groq API key

    Returns:
        dict with extracted bill data

    Raises:
        ValueError: If API key is missing or response can't be parsed
    """
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to your .env file.")

    client = Groq(api_key=api_key)

    ext = os.path.splitext(file_name)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
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
        temperature=0.0,  # Maximum determinism for accuracy
        max_completion_tokens=4096,  # More room for detailed extraction
    )

    raw = response.choices[0].message.content

    # Extract JSON block using regex to handle the <thinking> prefix
    json_match = re.search(r"```(?:json)?(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Fallback if model forgot fences but provided JSON at the end
        if "{" in raw:
            json_str = raw[raw.find("{"):raw.rfind("}")+1]
        else:
            json_str = raw.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"AI returned invalid JSON. Raw response:\n{raw[:1000]}\n\nError: {e}"
        )

    return data
