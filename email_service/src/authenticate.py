import os
import pickle
import sys

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
DATA_DIR = os.environ.get('DATA_DIR', '/app/data')
CREDENTIALS_PATH = os.path.join(DATA_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(DATA_DIR, 'token.json')


def authenticate():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                print(f"Error: {CREDENTIALS_PATH} not found.")
                print("Please mount your credentials.json to the data directory.")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=8080)
        
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
        print(f"Token saved to {TOKEN_PATH}")
    
    return creds


if __name__ == '__main__':
    print("Starting Gmail authentication...")
    authenticate()
    print("Authentication successful!")
