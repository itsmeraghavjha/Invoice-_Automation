import os
import time
import json
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from tenacity import retry, retry_if_exception_type, wait_fixed

class InvoiceExtractor:
    def __init__(self, api_key):
        # FIX 1: The model MUST be 'gemini-1.5-flash' or 'gemini-2.0-flash'. 2.5 does not exist.
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    @retry(retry=retry_if_exception_type(ResourceExhausted), wait=wait_fixed(30))
    def _generate(self, file_path, prompt):
        # FIX 2: Prevent the 400 Error by checking if the file is empty (0 bytes) before uploading.
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            print(f"⚠️ Skipping upload: File {file_path} is empty or corrupted.")
            return {} 

        # FIX 3: Catch the 400 API connection drop and retry safely.
        g_file = None
        for attempt in range(3):
            try:
                g_file = genai.upload_file(file_path)
                break
            except Exception as e:
                if attempt == 2:
                    raise Exception(f"Gemini API rejected the file upload: {e}")
                time.sleep(2)
        
        while g_file.state.name == "PROCESSING":
            time.sleep(1)
            g_file = genai.get_file(g_file.name)

        if g_file.state.name == "FAILED":
            raise Exception("Gemini processing failed")

        try:
            # Robust Text Mode (Manual JSON cleanup)
            result = self.model.generate_content([prompt, g_file])
            
            text = result.text.strip()
            # Clean markdown formatting if present
            if text.startswith("```json"): text = text[7:]
            elif text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            
            return json.loads(text.strip())
        finally:
            if g_file:
                try: genai.delete_file(g_file.name)
                except: pass

    def process_file(self, file_path):
        prompt = """
        Analyze this invoice and return a valid JSON object. 

        CRITICAL RULES FOR 'po_numbers':
        1. SAP Purchase Order numbers MUST be exactly 10 digits long.
        2. Valid PO numbers strictly fall within the range of 3300000000 to 8259999999.
        3. Do NOT extract Sales Orders (e.g., starting with 'SO' or 'DISSO').
        4. EXCEPTION: Some vendors print the 10-digit SAP PO under the label "Reference No.". If a number is exactly 10 digits and in the valid range, ALWAYS extract it, regardless of the label. Only ignore SHORT (under 10 digits) reference numbers.
        5. If no number matches these exact criteria, return an empty array [] for po_numbers.

        CRITICAL RULES FOR 'invoice_number' (Reference):
        1. This is the unique bill number provided by the vendor. Look for labels like "Invoice No", "Bill No", "Tax Invoice Number", or "Document No".
        2. DO NOT extract the 15-character GSTIN (Goods and Services Tax Identification Number).
        3. DO NOT extract the 10-character PAN (Permanent Account Number).
        4. DO NOT extract the PO number, GRN (Goods Receipt Note), or Internal Order numbers as the invoice number.
        5. It may contain slashes (/), hyphens (-), and financial year indicators (like 25-26).

        Required JSON Structure:
        {
            "invoice_number": "string",
            "invoice_date": "string",
            "po_numbers": ["string"],
            "vendor_name": "string",
            "first_line_item_description": "string",
            "net_amount": number,
            "gross_amount": number
        }
        """
        return self._generate(file_path, prompt)

    def process_non_po_file(self, file_path):
        prompt = """
        Analyze this Non-PO invoice and return a valid JSON object.

        CRITICAL RULE FOR 'withholding_tax_base' (TDS):
        1. Look for explicit TDS deductions ("Less TDS"). 
        2. If TDS is NOT explicitly printed on the document (like in freight bills), extract the TAXABLE VALUE (the total amount before GST is applied) as the withholding_tax_base.
        
        CRITICAL RULE FOR 'invoice_number':
        1. Do NOT extract GSTIN, PAN, or SAC codes as the invoice number.
        2. Look for "Bill No", "Invoice No", or "L.R. No".

        Required JSON Structure:
        {
            "invoice_number": "string",
            "invoice_date": "string",
            "header_text": "string",
            "withholding_tax_base": number,
            "gross_amount": number,
            "line_items": [
                {
                    "item_text": "string",
                    "item_gross_value": number,
                    "hsn_code": "string"
                }
            ]
        }
        """
        return self._generate(file_path, prompt)