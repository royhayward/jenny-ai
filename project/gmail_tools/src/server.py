import os
import re
import json
import pickle
import base64
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from mcp.server.fastmcp import FastMCP

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
DATA_DIR = os.environ.get('DATA_DIR', '/app/data')
CREDENTIALS_PATH = os.path.join(DATA_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(DATA_DIR, 'token.json')
WHITELIST_PATH = os.path.join(DATA_DIR, 'whitelist.json')

mcp = FastMCP(
    name="Gmail Unsubscribe Manager",
    host="0.0.0.0",
    port=int(os.environ.get('MCP_PORT', 8000))
)


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'wb') as token:
                pickle.dump(creds, token)
        else:
            raise Exception("No valid Gmail credentials. Run authentication first.")
    return build('gmail', 'v1', credentials=creds)


def load_whitelist() -> list:
    if os.path.exists(WHITELIST_PATH):
        with open(WHITELIST_PATH, 'r') as f:
            return json.load(f)
    return []


def save_whitelist(whitelist: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(WHITELIST_PATH, 'w') as f:
        json.dump(whitelist, f, indent=2)


def parse_timeframe(timeframe: str) -> datetime:
    match = re.match(r'(\d+)([dwm])', timeframe.lower())
    if not match:
        return datetime.utcnow() - timedelta(days=30)
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'd':
        return datetime.utcnow() - timedelta(days=value)
    elif unit == 'w':
        return datetime.utcnow() - timedelta(weeks=value)
    elif unit == 'm':
        return datetime.utcnow() - timedelta(days=value * 30)
    return datetime.utcnow() - timedelta(days=30)


def get_message_body(message: dict) -> str:
    payload = message.get('payload', {})
    parts = payload.get('parts', [payload])
    body = ""
    for part in parts:
        mime_type = part.get('mimeType', '')
        if mime_type == 'text/html' or mime_type == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        if part.get('parts'):
            for subpart in part['parts']:
                mime_type = subpart.get('mimeType', '')
                if mime_type == 'text/html' or mime_type == 'text/plain':
                    data = subpart.get('body', {}).get('data', '')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    return body


def extract_unsubscribe_info(message: dict) -> dict:
    headers = message.get('payload', {}).get('headers', [])
    unsubscribe_header = None
    for header in headers:
        if header['name'].lower() == 'list-unsubscribe':
            unsubscribe_header = header['value']
            break
    
    body = get_message_body(message)
    unsubscribe_links = []
    
    if unsubscribe_header:
        match = re.search(r'<(https?://[^>]+)>', unsubscribe_header)
        if match:
            unsubscribe_links.append({
                'type': 'header_link',
                'value': match.group(1),
                'source': 'List-Unsubscribe header'
            })
        elif unsubscribe_header.startswith('http'):
            unsubscribe_links.append({
                'type': 'header_link',
                'value': unsubscribe_header,
                'source': 'List-Unsubscribe header'
            })
    
    if body:
        soup = BeautifulSoup(body, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower()
            if 'unsubscribe' in href.lower() or 'unsubscribe' in text or 'opt-out' in text or 'opt out' in text:
                unsubscribe_links.append({
                    'type': 'body_link',
                    'value': href,
                    'source': f"Link text: '{link.get_text().strip()[:50]}'"
                })
        
        patterns = [
            r'unsubscribe[:\s]+(reply[^.]+)',
            r'to unsubscribe[,:\s]+([^.]+)',
            r'reply with ["\']?UNSUBSCRIBE["\']?',
            r'send an? email to ([\w\.-]+@[\w\.-]+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            for match in matches:
                unsubscribe_links.append({
                    'type': 'instruction',
                    'value': match.strip() if isinstance(match, str) else match[0].strip(),
                    'source': 'Text instruction in email body'
                })
    
    seen = set()
    unique_links = []
    for link in unsubscribe_links:
        if link['value'] not in seen:
            seen.add(link['value'])
            unique_links.append(link)
    
    return unique_links


def get_sender(message: dict) -> str:
    headers = message.get('payload', {}).get('headers', [])
    for header in headers:
        if header['name'].lower() == 'from':
            return header['value']
    return "Unknown"


def get_subject(message: dict) -> str:
    headers = message.get('payload', {}).get('headers', [])
    for header in headers:
        if header['name'].lower() == 'subject':
            return header['value']
    return "No Subject"


@mcp.tool()
async def filter_emails(
    search_term: str,
    status: str = "all",
    timeframe: str = "30d",
    max_results: int = 50,
    exclude_whitelisted: bool = True
) -> str:
    """
    Search Gmail for emails and extract unsubscribe information.
    
    Args:
        search_term: Keyword to search for (e.g., "unsubscribe", "newsletter")
        status: Filter by read status - "unread", "read", or "all"
        timeframe: Time period to search - format: "30d", "2w", "1m"
        max_results: Maximum number of emails to return
        exclude_whitelisted: Exclude emails from whitelisted senders
    
    Returns:
        JSON string with matching emails and their unsubscribe info
    """
    try:
        service = get_gmail_service()
    except Exception as e:
        return json.dumps({"error": str(e)})
    
    whitelist = load_whitelist() if exclude_whitelisted else []
    whitelist_emails = [w.lower() for w in whitelist]
    
    after_date = parse_timeframe(timeframe)
    query = f'after:{after_date.strftime("%Y/%m/%d")} "{search_term}"'
    
    if status == "unread":
        query += " is:unread"
    elif status == "read":
        query += " is:read"
    
    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        messages = results.get('messages', [])
    except Exception as e:
        return json.dumps({"error": f"Gmail API error: {str(e)}"})
    
    email_results = []
    
    for msg in messages:
        try:
            message = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()
            
            sender = get_sender(message)
            sender_email = re.search(r'[\w\.-]+@[\w\.-]+', sender)
            sender_email = sender_email.group(0).lower() if sender_email else sender.lower()
            
            if exclude_whitelisted and sender_email in whitelist_emails:
                continue
            
            subject = get_subject(message)
            unsubscribe_info = extract_unsubscribe_info(message)
            
            email_results.append({
                'message_id': msg['id'],
                'sender': sender,
                'subject': subject,
                'unsubscribe_options': unsubscribe_info
            })
        except Exception as e:
            continue
    
    return json.dumps({
        'total_found': len(email_results),
        'emails': email_results
    }, indent=2)


@mcp.tool()
async def unsubscribe_action(
    unsubscribe_info: str,
    action_type: str = "link",
    sender: Optional[str] = None,
    message_id: Optional[str] = None,
    confirm: bool = False
) -> str:
    """
    Execute an unsubscribe action.
    
    Args:
        unsubscribe_info: The unsubscribe URL or instruction
        action_type: Type of action - "link" (HTTP GET) or "instruction" (send email)
        sender: Sender email address (for instruction-based unsubscribe)
        message_id: Gmail message ID for post-action (mark read, label)
        confirm: Set to True to actually execute the action
    
    Returns:
        Result of the unsubscribe action
    """
    if not confirm:
        return json.dumps({
            "status": "preview",
            "message": "Action not executed. Set confirm=True to execute.",
            "action_type": action_type,
            "unsubscribe_info": unsubscribe_info
        })
    
    result = {"action_type": action_type, "success": False}
    
    if action_type == "link":
        try:
            response = requests.get(unsubscribe_info, timeout=10, allow_redirects=True)
            result["success"] = response.status_code < 400
            result["http_status"] = response.status_code
            result["final_url"] = response.url
            result["message"] = "Unsubscribe link visited successfully" if result["success"] else f"Request failed with status {response.status_code}"
        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Failed to visit unsubscribe link: {e}"
    
    elif action_type == "instruction":
        if not sender:
            return json.dumps({"error": "Sender email required for instruction-based unsubscribe"})
        
        try:
            service = get_gmail_service()
            
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', unsubscribe_info)
            to_email = email_match.group(0) if email_match else sender
            
            message_body = {
                'raw': base64.urlsafe_b64encode(
                    f"To: {to_email}\r\n"
                    f"Subject: UNSUBSCRIBE\r\n\r\n"
                    f"Please unsubscribe me from your mailing list.\r\n".encode()
                ).decode()
            }
            
            sent = service.users().messages().send(userId='me', body=message_body).execute()
            result["success"] = True
            result["message"] = f"Unsubscribe email sent to {to_email}"
            result["sent_message_id"] = sent.get('id')
        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Failed to send unsubscribe email: {e}"
    
    if result["success"] and message_id:
        try:
            service = get_gmail_service()
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            label_result = service.users().labels().list(userId='me').execute()
            labels = {l['name']: l['id'] for l in label_result.get('labels', [])}
            
            if 'Unsubscribed' not in labels:
                label = service.users().labels().create(
                    userId='me',
                    body={'name': 'Unsubscribed', 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
                ).execute()
                label_id = label['id']
            else:
                label_id = labels['Unsubscribed']
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            
            result["post_action"] = "Email marked as read and labeled 'Unsubscribed'"
        except Exception as e:
            result["post_action_warning"] = str(e)
    
    return json.dumps(result, indent=2)


@mcp.tool()
async def whitelist_add(email_address: str) -> str:
    """
    Add an email address to the whitelist.
    
    Args:
        email_address: Email address to whitelist
    
    Returns:
        Confirmation message
    """
    whitelist = load_whitelist()
    email_lower = email_address.lower()
    
    if email_lower in [e.lower() for e in whitelist]:
        return json.dumps({"status": "already_exists", "email": email_address})
    
    whitelist.append(email_address)
    save_whitelist(whitelist)
    
    return json.dumps({"status": "added", "email": email_address, "total_whitelisted": len(whitelist)})


@mcp.tool()
async def whitelist_remove(email_address: str) -> str:
    """
    Remove an email address from the whitelist.
    
    Args:
        email_address: Email address to remove
    
    Returns:
        Confirmation message
    """
    whitelist = load_whitelist()
    email_lower = email_address.lower()
    
    original_count = len(whitelist)
    whitelist = [e for e in whitelist if e.lower() != email_lower]
    
    if len(whitelist) == original_count:
        return json.dumps({"status": "not_found", "email": email_address})
    
    save_whitelist(whitelist)
    
    return json.dumps({"status": "removed", "email": email_address, "total_whitelisted": len(whitelist)})


@mcp.tool()
async def whitelist_list() -> str:
    """
    List all whitelisted email addresses.
    
    Returns:
        JSON array of whitelisted emails
    """
    whitelist = load_whitelist()
    return json.dumps({"count": len(whitelist), "emails": whitelist}, indent=2)


@mcp.tool()
async def check_authentication() -> str:
    """
    Check if Gmail authentication is valid.
    
    Returns:
        Authentication status
    """
    try:
        if not os.path.exists(TOKEN_PATH):
            return json.dumps({
                "authenticated": False,
                "message": "No token found. Run authentication first.",
                "token_path": TOKEN_PATH
            })
        
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
        
        if creds.valid:
            return json.dumps({"authenticated": True, "message": "Credentials are valid"})
        elif creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'wb') as token:
                pickle.dump(creds, token)
            return json.dumps({"authenticated": True, "message": "Credentials refreshed successfully"})
        else:
            return json.dumps({
                "authenticated": False,
                "message": "Credentials are invalid and cannot be refreshed"
            })
    except Exception as e:
        return json.dumps({
            "authenticated": False,
            "error": str(e),
            "message": "Error checking authentication"
        })


if __name__ == "__main__":
    mcp.run(transport="sse")
