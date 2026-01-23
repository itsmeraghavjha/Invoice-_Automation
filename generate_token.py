import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import Config

def generate_token():
    creds = None
    # 1. Check if token.json already exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', Config.SCOPES)
    
    # 2. If no valid credentials, let's log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🔐 Initiating Login...")
            # Make sure credentials.json is in the same folder
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', Config.SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 3. Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("✅ 'token.json' generated successfully!")

if __name__ == '__main__':
    generate_token()