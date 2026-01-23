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
import google.generativeai as genai
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
    # Regex looks for at least 3 letters (Month) and 2-4 digits (Year)
    # e.g. "January 2025", "Jan 25", "Invoices Dec 2024"
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
def process_po_invoice(pdf_info):
    db = HistoryDB(Config.DB_FILE)
    if db.is_processed(pdf_info['id']): 
        db.close()
        return None
    db.close()

    time.sleep(random.uniform(0.5, 1.5))
    print(f"  [PO] Processing: {pdf_info['name']}")
    temp_path = f"temp_po_{pdf_info['id']}.pdf"
    
    try:
        local_drive = DriveTool(Config) 
        local_ai = InvoiceExtractor(Config.GEMINI_API_KEY) 

        pdf_bytes = local_drive.download_pdf(pdf_info['id'])
        with open(temp_path, "wb") as f: f.write(pdf_bytes.getbuffer())
        
        data = local_ai.process_file(temp_path) 
        
        if isinstance(data, list): data = data[0] if data else {}

        pos = data.get('po_numbers', [])
        if isinstance(pos, str): pos = [pos]
        if not pos: pos = []

        db = HistoryDB(Config.DB_FILE)
        db.log_success(pdf_info['id'])
        db.close()
        
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
def process_non_po_invoice(pdf_info):
    db = HistoryDB(Config.DB_FILE)
    if db.is_processed(pdf_info['id']): 
        db.close()
        return None
    db.close()

    time.sleep(random.uniform(0.5, 1.5))
    print(f"  [Non-PO] Processing: {pdf_info['name']}")
    temp_path = f"temp_npo_{pdf_info['id']}.pdf"
    
    try:
        local_drive = DriveTool(Config) 
        local_ai = InvoiceExtractor(Config.GEMINI_API_KEY)

        vendor_no, cost_center = parse_filename_metadata(pdf_info['name'])
        pdf_bytes = local_drive.download_pdf(pdf_info['id'])
        with open(temp_path, "wb") as f: f.write(pdf_bytes.getbuffer())
        
        data = local_ai.process_non_po_file(temp_path) 
        
        if isinstance(data, list): data = data[0] if data else {}

        db = HistoryDB(Config.DB_FILE)
        db.log_success(pdf_info['id'])
        db.close()
        
        # ADDED 'Document Link' HERE
        return {
            'Vendor No': vendor_no,
            'Inv Date': normalize_date(data.get('invoice_date')),
            'Reference': data.get('invoice_number'),
            'Amount': data.get('gross_amount'),
            'Amount in Doc.Currency (Item Wise)': data.get('gross_amount'),
            'Item text': data.get('header_text'),
            'Cost center': cost_center,
            'HSN/SAC': data.get('hsn_sac'),
            'With Holding tax Base Amount': data.get('withholding_tax_base'),
            'Document Link': pdf_info.get('webViewLink')
        }
    except Exception as e:
        print(f"  ❌ Error on {pdf_info['name']}: {e}")
        return None
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# --- SMART SCANNER ---
def scan_and_process(drive_tool, root_id, worker_func, results_list):
    """
    Intelligently scans for folders.
    Strategy 1: Check if root contains Date Folders (e.g., 'Jan 2025').
    Strategy 2: Check if root contains Regions -> Date Folders.
    """
    try:
        root_subs = drive_tool.list_files(root_id, "application/vnd.google-apps.folder")
        if not root_subs:
            print("     (Folder is empty)")
            return

        # Check for Strategy 1 (Direct Date Folders)
        date_folders = [f for f in root_subs if parse_smart_date(f['name'])]
        
        targets = []
        
        if date_folders:
            print(f"     👉 Detected Simple Structure (Found {len(date_folders)} date folders)")
            # Sort newest first
            targets.append(sorted(date_folders, key=lambda x: parse_smart_date(x['name']), reverse=True)[0])
        else:
            print("     👉 Checking for Region Structure (e.g. Region -> Date Folder)...")
            for region in root_subs:
                sub_subs = drive_tool.list_files(region['id'], "application/vnd.google-apps.folder")
                valid_dates = [s for s in sub_subs if parse_smart_date(s['name'])]
                if valid_dates:
                    best_sub = sorted(valid_dates, key=lambda x: parse_smart_date(x['name']), reverse=True)[0]
                    # Rename for clarity in logs
                    best_sub['name'] = f"{region['name']}/{best_sub['name']}"
                    targets.append(best_sub)
                else:
                    print(f"        ⚠️ Skipped '{region['name']}': No date subfolders (e.g. 'Jan 2025') found inside.")

        if not targets:
            print("     ❌ No valid 'Month Year' folders found. Please create a folder like 'January 2025'.")
            return

        # Process identified targets
        for target in targets:
            print(f"     📍 Scanning: {target['name']}")
            pdfs = drive_tool.list_files(target['id'], "application/pdf")
            
            if not pdfs:
                print("        (No PDFs found)")
                continue

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(worker_func, p) for p in pdfs]
                for f in concurrent.futures.as_completed(futures):
                    if res := f.result(): results_list.append(res)

    except Exception as e:
        print(f"❌ Scan Error: {e}")

# --- MAIN ---
def main():
    print("🤖 Agent Starting...")
    
    if not Config.GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY not found in environment variables.")
        return
    
    genai.configure(api_key=Config.GEMINI_API_KEY)
    
    try:
        init_db = HistoryDB(Config.DB_FILE)
        init_db.close()
    except Exception as e:
        print(f"❌ DB Init Failed: {e}")
        return

    try:
        master_drive = DriveTool(Config)
        email = EmailSender(Config) 
    except Exception as e:
        print(f"❌ Init Failed: {e}")
        return

    po_results = []
    non_po_results = []

    # === CYCLE 1: PO INVOICES ===
    if Config.ROOT_FOLDER_ID:
        print(f"\n📂 Scanning PO Folders (ID: {Config.ROOT_FOLDER_ID})...")
        scan_and_process(master_drive, Config.ROOT_FOLDER_ID, process_po_invoice, po_results)

    # === CYCLE 2: NON-PO INVOICES ===
    if Config.NON_PO_FOLDER_ID:
        print(f"\n📂 Scanning Non-PO Folders (ID: {Config.NON_PO_FOLDER_ID})...")
        scan_and_process(master_drive, Config.NON_PO_FOLDER_ID, process_non_po_invoice, non_po_results)

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

        # ADDED 'Document Link' TO COLUMNS
        cols_npo = ['SL No', 'Vendor No', 'Inv Date', 'Reference', 'Amount', 
                    'Amount in Doc.Currency (Item Wise)', 'Item text', 
                    'Cost center', 'HSN/SAC', 'With Holding tax Base Amount', 'Document Link']
        
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