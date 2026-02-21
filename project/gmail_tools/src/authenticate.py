import os
import pickle
import sys

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def authenticate():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        with open('token.json', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check for credentials.json at /app/credentials.json
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found.")
                print("Please ensure credentials.json is mounted at /app/credentials.json inside the container.")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        # Save the credentials for the next run
        with open('token.json', 'wb') as token:
            pickle.dump(creds, token)
    return creds

if __name__ == '__main__':
    print("Starting authentication process...")
    authenticate()
    print("Authentication successful! Token saved to token.json.")
