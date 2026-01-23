import time
import json
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from tenacity import retry, retry_if_exception_type, wait_fixed

class InvoiceExtractor:
    def __init__(self, api_key):
        # NOTE: genai.configure is handled in main.py
        # FIX: Changed 'gemini-2.5-flash' (invalid) to 'gemini-1.5-flash' (valid)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    @retry(retry=retry_if_exception_type(ResourceExhausted), wait=wait_fixed(30))
    def _generate(self, file_path, prompt):
        g_file = genai.upload_file(file_path)
        
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
            try: genai.delete_file(g_file.name)
            except: pass

    def process_file(self, file_path):
        prompt = """
        Analyze this invoice and return a valid JSON object. 
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
        Required JSON Structure:
        {
            "invoice_number": "string",
            "invoice_date": "string",
            "header_text": "string",
            "hsn_sac": "string",
            "withholding_tax_base": number,
            "gross_amount": number
        }
        """
        return self._generate(file_path, prompt)