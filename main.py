# import os
# import re
# import time
# import random
# import pandas as pd
# import concurrent.futures
# from datetime import datetime
# from dateutil import parser as date_parser 
# from config import Config
# from modules.drive_tool import DriveTool # <--- Class imported
# from modules.ai_tool import InvoiceExtractor 
# from modules.database import HistoryDB
# from modules.email_tool import EmailSender 

# # --- DATE HELPER ---
# def normalize_date(date_str):
#     if not date_str: return None
#     try:
#         dt = date_parser.parse(str(date_str), dayfirst=True)
#         return dt.strftime("%d.%m.%Y") 
#     except:
#         return date_str

# def parse_smart_date(folder_name):
#     match = re.search(r'([a-zA-Z]{3,})[^0-9]*(\d{2,4})', folder_name)
#     if not match: return None
#     month, year = match.groups()
#     if len(year) == 2: year = "20" + year
#     try: return datetime.strptime(f"{month} {year}", "%b %Y")
#     except: return None

# # --- WORKER FUNCTION ---
# # REMOVED 'drive' from arguments. It is now created inside.
# def process_single_pdf(pdf_info, memory):
#     if memory.is_processed(pdf_info['id']):
#         return None

#     # 1. Jitter (prevents network collision)
#     time.sleep(random.uniform(0.5, 1.5))

#     # 2. ISOLATION: Create FRESH connections for this specific thread
#     # This prevents threads from waiting on each other.
#     local_drive = DriveTool(Config) 
#     local_ai = InvoiceExtractor(Config.GEMINI_API_KEY)

#     print(f"  🚀 Processing: {pdf_info['name']}")
#     temp_path = f"temp_{pdf_info['id']}.pdf"
    
#     try:
#         # 3. Download using the LOCAL drive connection
#         pdf_bytes = local_drive.download_pdf(pdf_info['id'])
#         with open(temp_path, "wb") as f: f.write(pdf_bytes.getbuffer())
        
#         # 4. Process using the LOCAL AI connection
#         data = local_ai.process_file(temp_path)
        
#         pos = data.get('po_numbers', [])
#         if isinstance(pos, str): pos = [pos]
#         if not pos: pos = []

#         formatted_date = normalize_date(data.get('invoice_date'))
#         memory.log_success(pdf_info['id'])
        
#         return {
#             'Document Date': formatted_date,
#             'Purchasing Doc. 1': pos[0] if len(pos)>0 else None,
#             'Purchasing Doc. 2': pos[1] if len(pos)>1 else None, 
#             'Purchasing Doc. 3': pos[2] if len(pos)>2 else None, 
#             'Reference': data.get('invoice_number'),
#             'Document Header Text': data.get('first_line_item_description'),
#             'Gross Value': data.get('gross_amount'),
#             'Net Value': data.get('net_amount'),
#             'Document Link': pdf_info.get('webViewLink')
#         }

#     except Exception as e:
#         print(f"  ❌ Error on {pdf_info['name']}: {e}")
#         return None
#     finally:
#         if os.path.exists(temp_path): os.remove(temp_path)

# # --- MAIN ORCHESTRATOR ---
# def main():
#     print("🤖 Agent Starting (Fully Isolated Parallel Mode)...")
#     try:
#         # We need one Drive instance just to list the folders initially
#         master_drive = DriveTool(Config)
#         memory = HistoryDB(Config.DB_FILE)
#         email = EmailSender(Config) 
#     except Exception as e:
#         print(f"❌ Initialization Failed: {e}")
#         return

#     print("📂 Scanning Drive...")
#     try:
#         regions = master_drive.list_files(Config.ROOT_FOLDER_ID, "application/vnd.google-apps.folder")
#     except Exception as e:
#         print(f"❌ Drive Error: {e}")
#         return
    
#     all_report_data = []

#     for region in regions:
#         sub_folders = master_drive.list_files(region['id'], "application/vnd.google-apps.folder")
#         valid_folders = []
#         for s in sub_folders:
#             dt = parse_smart_date(s['name'])
#             if dt: valid_folders.append({'id': s['id'], 'name': s['name'], 'date': dt})
        
#         if not valid_folders: continue
            
#         valid_folders.sort(key=lambda x: x['date'], reverse=True)
#         target_folder = valid_folders[0]

#         print(f"📍 Region: {region['name']} -> Target: {target_folder['name']}")
#         pdfs = master_drive.list_files(target_folder['id'], "application/pdf")
        
#         # INCREASE WORKERS TO 5 (Since connections are now isolated, it's safer)
#         with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#             # We only pass the PDF info and memory. Drive/AI are built inside.
#             futures = [executor.submit(process_single_pdf, pdf, memory) for pdf in pdfs]
            
#             for future in concurrent.futures.as_completed(futures):
#                 result = future.result()
#                 if result:
#                     all_report_data.append(result)

#     if all_report_data:
#         df = pd.DataFrame(all_report_data)
#         csv_name = "report.csv"
        
#         internal_cols = ['Document Date', 'Purchasing Doc. 1', 'Purchasing Doc. 2', 'Purchasing Doc. 3', 
#                          'Reference', 'Document Header Text', 'Gross Value', 'Net Value', 'Document Link']
        
#         df = df.reindex(columns=internal_cols)
#         df.columns = ['Document Date', 'Purchasing Doc.', 'Purchasing Doc.', 'Purchasing Doc.', 
#                       'Reference', 'Document Header Text', 'Gross Value', 'Net Value', 'Document Link']
        
#         df.to_csv(csv_name, index=False)
#         print(f"✅ Cycle Complete. {len(all_report_data)} invoices processed.")
        
#         try:
#             email.send_report(csv_name, len(all_report_data))
#         except Exception as e:
#             print(f"⚠️ Email failed: {e}")
#         finally:
#             if os.path.exists(csv_name):
#                 os.remove(csv_name)
#     else:
#         print("✅ Cycle Complete. No new invoices found.")

# if __name__ == "__main__":
#     main()


import os
import re
import time
import random
import pandas as pd
import concurrent.futures
from datetime import datetime
from dateutil import parser as date_parser 
from config import Config
from modules.drive_tool import DriveTool
from modules.ai_tool import InvoiceExtractor 
from modules.database import HistoryDB
from modules.email_tool import EmailSender 

# --- HELPERS ---
def normalize_date(date_str):
    if not date_str: return None
    try:
        dt = date_parser.parse(str(date_str), dayfirst=True)
        return dt.strftime("%d.%m.%Y") 
    except:
        return date_str

def parse_smart_date(folder_name):
    match = re.search(r'([a-zA-Z]{3,})[^0-9]*(\d{2,4})', folder_name)
    if not match: return None
    month, year = match.groups()
    if len(year) == 2: year = "20" + year
    try: return datetime.strptime(f"{month} {year}", "%b %Y")
    except: return None

def parse_filename_metadata(filename):
    clean_name = os.path.splitext(filename)[0] 
    parts = clean_name.split('-')
    if len(parts) >= 2:
        vendor = parts[0].strip()
        cost_center = f"{parts[1].strip()}COMN"
        return vendor, cost_center
    else:
        return clean_name, ""

# --- WORKER: PO INVOICES ---
def process_po_invoice(pdf_info, memory):
    if memory.is_processed(pdf_info['id']): return None
    time.sleep(random.uniform(0.5, 1.5))
    
    print(f"  [PO] Processing: {pdf_info['name']}")
    temp_path = f"temp_po_{pdf_info['id']}.pdf"
    
    try:
        local_drive = DriveTool(Config) 
        # 🔧 FIX: Pass API Key here
        local_ai = InvoiceExtractor(Config.GEMINI_API_KEY) 

        pdf_bytes = local_drive.download_pdf(pdf_info['id'])
        with open(temp_path, "wb") as f: f.write(pdf_bytes.getbuffer())
        
        data = local_ai.process_file(temp_path) 
        
        # Guard against List vs Dict return
        if isinstance(data, list):
            data = data[0] if data else {}

        pos = data.get('po_numbers', [])
        if isinstance(pos, str): pos = [pos]
        if not pos: pos = []

        memory.log_success(pdf_info['id'])
        
        return {
            'Document Date': normalize_date(data.get('invoice_date')),
            'Purchasing Doc. 1': pos[0] if len(pos)>0 else None,
            'Purchasing Doc. 2': pos[1] if len(pos)>1 else None, 
            'Purchasing Doc. 3': pos[2] if len(pos)>2 else None,
            'Reference': data.get('invoice_number'),
            'Document Header Text': data.get('first_line_item_description'),
            'Gross Value': data.get('gross_amount'),
            'Net Value': data.get('net_amount'),
            'Document Link': pdf_info.get('webViewLink')
        }
    except Exception as e:
        print(f"  ❌ Error on {pdf_info['name']}: {e}")
        return None
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# --- WORKER: NON-PO INVOICES ---
def process_non_po_invoice(pdf_info, memory):
    if memory.is_processed(pdf_info['id']): return None
    time.sleep(random.uniform(0.5, 1.5))
    
    print(f"  [Non-PO] Processing: {pdf_info['name']}")
    temp_path = f"temp_npo_{pdf_info['id']}.pdf"
    
    try:
        local_drive = DriveTool(Config) 
        # 🔧 FIX: Pass API Key here
        local_ai = InvoiceExtractor(Config.GEMINI_API_KEY)

        vendor_no, cost_center = parse_filename_metadata(pdf_info['name'])
        pdf_bytes = local_drive.download_pdf(pdf_info['id'])
        with open(temp_path, "wb") as f: f.write(pdf_bytes.getbuffer())
        
        data = local_ai.process_non_po_file(temp_path) 
        
        # Guard against List vs Dict return
        if isinstance(data, list):
            data = data[0] if data else {}

        memory.log_success(pdf_info['id'])
        
        return {
            'Vendor No': vendor_no,
            'Inv Date': normalize_date(data.get('invoice_date')),
            'Reference': data.get('invoice_number'),
            'Amount': data.get('gross_amount'),
            'Amount in Doc.Currency (Item Wise)': data.get('gross_amount'),
            'Item text': data.get('header_text'),
            'Cost center': cost_center,
            'HSN/SAC': data.get('hsn_sac'),
            'With Holding tax Base Amount': data.get('withholding_tax_base')
        }
    except Exception as e:
        print(f"  ❌ Error on {pdf_info['name']}: {e}")
        return None
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# --- MAIN ---
def main():
    print("🤖 Agent Starting...")
    try:
        master_drive = DriveTool(Config)
        memory = HistoryDB(Config.DB_FILE)
        email = EmailSender(Config) 
    except Exception as e:
        print(f"❌ Init Failed: {e}")
        return

    po_results = []
    non_po_results = []

    # === CYCLE 1: PO INVOICES ===
    if Config.ROOT_FOLDER_ID:
        print(f"\n📂 Scanning PO Folders (ID: {Config.ROOT_FOLDER_ID})...")
        try:
            regions = master_drive.list_files(Config.ROOT_FOLDER_ID, "application/vnd.google-apps.folder")
            for region in regions:
                sub = master_drive.list_files(region['id'], "application/vnd.google-apps.folder")
                valid = [s for s in sub if parse_smart_date(s['name'])]
                if not valid: continue
                target = sorted(valid, key=lambda x: parse_smart_date(x['name']), reverse=True)[0]
                
                pdfs = master_drive.list_files(target['id'], "application/pdf")
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                    futures = [ex.submit(process_po_invoice, p, memory) for p in pdfs]
                    for f in concurrent.futures.as_completed(futures):
                        if res := f.result(): po_results.append(res)
        except Exception as e:
            print(f"❌ PO Cycle Error: {e}")

    # === CYCLE 2: NON-PO INVOICES ===
    if Config.NON_PO_FOLDER_ID:
        print(f"\n📂 Scanning Non-PO Folders (ID: {Config.NON_PO_FOLDER_ID})...")
        try:
            regions = master_drive.list_files(Config.NON_PO_FOLDER_ID, "application/vnd.google-apps.folder")
            for region in regions:
                sub = master_drive.list_files(region['id'], "application/vnd.google-apps.folder")
                valid = [s for s in sub if parse_smart_date(s['name'])]
                if not valid: continue
                target = sorted(valid, key=lambda x: parse_smart_date(x['name']), reverse=True)[0]
                
                pdfs = master_drive.list_files(target['id'], "application/pdf")
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                    futures = [ex.submit(process_non_po_invoice, p, memory) for p in pdfs]
                    for f in concurrent.futures.as_completed(futures):
                        if res := f.result(): non_po_results.append(res)
        except Exception as e:
            print(f"❌ Non-PO Cycle Error: {e}")

    # === REPORTING ===
    
    if po_results:
        df_po = pd.DataFrame(po_results)
        cols_po = ['Document Date', 'Purchasing Doc. 1', 'Purchasing Doc. 2', 'Purchasing Doc. 3', 
                   'Reference', 'Document Header Text', 'Gross Value', 'Net Value', 'Document Link']
        df_po = df_po.reindex(columns=cols_po)
        
        csv_po = f"PO_Report_{datetime.now().strftime('%d%b')}.csv"
        df_po.to_csv(csv_po, index=False)
        print(f"✅ Generated {csv_po} ({len(po_results)} invoices)")
        try: email.send_report(csv_po, len(po_results))
        except: pass
        if os.path.exists(csv_po): os.remove(csv_po)

    if non_po_results:
        df_npo = pd.DataFrame(non_po_results)
        df_npo.insert(0, 'SL No', range(1, 1 + len(df_npo)))
        df_npo['SL No'] = df_npo['SL No'].astype(float)

        cols_npo = ['SL No', 'Vendor No', 'Inv Date', 'Reference', 'Amount', 
                    'Amount in Doc.Currency (Item Wise)', 'Item text', 
                    'Cost center', 'HSN/SAC', 'With Holding tax Base Amount']
        
        df_npo = df_npo.reindex(columns=cols_npo)
        
        csv_npo = f"FB60_Report_{datetime.now().strftime('%d%b')}.csv"
        df_npo.to_csv(csv_npo, index=False)
        print(f"✅ Generated {csv_npo} ({len(non_po_results)} invoices)")
        try: email.send_report(csv_npo, len(non_po_results))
        except: pass
        if os.path.exists(csv_npo): os.remove(csv_npo)

    if not po_results and not non_po_results:
        print("✅ No new invoices found.")

if __name__ == "__main__":
    main()