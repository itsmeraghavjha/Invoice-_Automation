# # config.py
# import os
# from dotenv import load_dotenv

# load_dotenv()

# class Config:
#     GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#     ROOT_FOLDER_ID = os.getenv("ROOT_FOLDER_ID")
#     GMAIL_USER = os.getenv("GMAIL_USER")
#     GMAIL_PASS = os.getenv("GMAIL_PASSWORD")
#     # RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
#     # --- ROBUST EMAIL PARSING ---
#     _email_raw = os.getenv("RECEIVER_EMAILS", "")
    
#     # Remove brackets [] and quotes '" if they exist
#     _email_clean = _email_raw.replace("[", "").replace("]", "").replace('"', "").replace("'", "")
    
#     # Split by comma and strip spaces
#     RECEIVER_EMAILS = [e.strip() for e in _email_clean.split(",") if e.strip()]
#     DB_FILE = "invoice_history.db"
#     SCOPES = ['https://www.googleapis.com/auth/drive.readonly']








# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ROOT_FOLDER_ID = os.getenv("ROOT_FOLDER_ID")       # Existing PO Folder
    NON_PO_FOLDER_ID = os.getenv("NON_PO_FOLDER_ID")   # <--- NEW: Add this in your .env too
    
    GMAIL_USER = os.getenv("GMAIL_USER")
    GMAIL_PASS = os.getenv("GMAIL_PASSWORD")
    
    # Email parsing
    _email_raw = os.getenv("RECEIVER_EMAILS", "")
    _email_clean = _email_raw.replace("[", "").replace("]", "").replace('"', "").replace("'", "")
    RECEIVER_EMAILS = [e.strip() for e in _email_clean.split(",") if e.strip()]
    
    DB_FILE = "invoice_history.db"
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']