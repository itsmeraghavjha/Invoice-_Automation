# import time
# import json
# import typing_extensions
# import google.generativeai as genai
# from google.api_core.exceptions import ResourceExhausted
# from tenacity import retry, retry_if_exception_type, wait_fixed

# # --- 1. DEFINE THE STRICT SCHEMA ---
# class InvoiceData(typing_extensions.TypedDict):
#     invoice_number: str
#     invoice_date: str
#     po_numbers: list[str]
#     vendor_name: str
#     first_line_item_description: str
#     net_amount: float
#     gross_amount: float

# class InvoiceExtractor:
#     def __init__(self, api_key):
#         genai.configure(api_key=api_key)
#         self.model = genai.GenerativeModel('gemini-2.5-flash')

#     @retry(retry=retry_if_exception_type(ResourceExhausted), wait=wait_fixed(30))
#     def process_file(self, file_path):
#         """Uploads and processes file. Retries automatically on 429 Quota errors."""
        
#         # 1. Upload
#         g_file = genai.upload_file(file_path)
        
#         # 2. Wait for processing
#         while g_file.state.name == "PROCESSING":
#             time.sleep(1)
#             g_file = genai.get_file(g_file.name)

#         if g_file.state.name == "FAILED":
#             raise Exception("Gemini processing failed")

#         # 3. Strict Prompt
#         prompt = """
#         Analyze this invoice document and extract specific fields into JSON. 
        
#         1. **Invoice Number**: Look for 'Invoice No', 'Bill No', 'Tax Invoice No'.
#         2. **Invoice Date**: The date of issue.
#         3. **PO Numbers**: Look for 'Purchase Order No', 'Buyer Order No', 'Order No', 'Customer PO'. 
#            **CRITICAL**: If there are MULTIPLE PO numbers, extract ALL of them into a list.
#         4. **Vendor Name**: The company selling the goods.
#         5. **first_line_item_description**: Description of the first item in the table.
#         6. **net_amount**: The TOTAL TAXABLE VALUE (before taxes).
#         7. **gross_amount**: The Grand Total / Invoice Total (including taxes).

#         Return null if a field is not found.
#         """
        
#         # 4. Generate with Schema Enforcement
#         try:
#             result = self.model.generate_content(
#                 [g_file, prompt],
#                 generation_config=genai.GenerationConfig(
#                     response_mime_type="application/json",
#                     response_schema=InvoiceData  # <--- THIS WAS MISSING
#                 )
#             )
#             return json.loads(result.text)
            
#         finally:
#             # 5. Cleanup
#             genai.delete_file(g_file.name)




import time
import json
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from tenacity import retry, retry_if_exception_type, wait_fixed

class InvoiceExtractor:
    def __init__(self, api_key):
        # 🔧 FIX: Configure explicitly inside the class
        genai.configure(api_key=api_key)
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