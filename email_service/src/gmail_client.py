import os
import pickle
import sys
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_gmail_service():
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
            print("Error: No valid Gmail credentials found.")
            print("Please run 'python src/authenticate.py' first to authenticate.")
            sys.exit(1)

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f"Error building Gmail service: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # This block is for testing the client independently
    print("Attempting to get Gmail service...")
    service = get_gmail_service()
    if service:
        print("Successfully obtained Gmail service object.")
        # Example: Print some labels to confirm access
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        print("Labels:")
        if not labels:
            print('No labels found.')
        else:
            for label in labels:
                print(label['name'])
    else:
        print("Failed to obtain Gmail service object.")
