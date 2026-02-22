# Gmail Unsubscribe Manager - MCP Server

An MCP (Model Context Protocol) server for managing Gmail email subscriptions. Integrates with opencode and other MCP clients.

## Features

- **filter_emails**: Search Gmail and extract unsubscribe links from emails
- **unsubscribe_action**: Execute unsubscribe actions (visit links or send emails)
- **whitelist_add/remove/list**: Manage trusted senders to exclude from unsubscribes
- **check_authentication**: Verify Gmail API credentials

## Prerequisites

1. Google Cloud Project with Gmail API enabled
2. OAuth 2.0 credentials (`credentials.json`)
3. Docker and Docker Compose

## Setup

### 1. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable the Gmail API
4. Go to "Credentials" > "Create Credentials" > "OAuth client ID"
5. Choose "Web application" or "Desktop application"
6. Add authorized redirect URI: `http://localhost:8080`
7. Download the credentials JSON file

### 2. Configure the Server

```bash
# Create data directory
mkdir -p data

# Copy your Google credentials
cp /path/to/credentials.json data/
```

### 3. Build and Run

Run from the project root (where `docker-compose.yml` is located):

```bash
# Build the Docker image
docker compose build

# Run authentication (first time only)
docker compose run --rm -p 8080:8080 email-service python src/authenticate.py

# Start the MCP server
docker compose up -d
```

The authentication step will open a browser for Google OAuth consent. After authorizing, the token is saved to `email_service/data/token.json`.

## opencode Integration

Add to your opencode MCP configuration:

```json
{
  "mcpServers": {
    "email-service": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Or if running locally without Docker:

```json
{
  "mcpServers": {
    "email-service": {
      "command": "python",
      "args": ["src/server.py"],
      "cwd": "/path/to/email_service"
    }
  }
}
```

## Available Tools

### filter_emails

Search Gmail for emails and extract unsubscribe information.

```json
{
  "search_term": "unsubscribe",
  "status": "all",
  "timeframe": "30d",
  "max_results": 50,
  "exclude_whitelisted": true
}
```

Returns emails with sender, subject, and unsubscribe options.

### unsubscribe_action

Execute an unsubscribe action.

```json
{
  "unsubscribe_info": "https://example.com/unsubscribe/abc123",
  "action_type": "link",
  "sender": "newsletter@example.com",
  "message_id": "msg123",
  "confirm": true
}
```

Set `confirm: true` to actually execute. Without confirmation, returns a preview.

### whitelist_add

Add sender to whitelist.

```json
{
  "email_address": "important@company.com"
}
```

### whitelist_remove

Remove sender from whitelist.

```json
{
  "email_address": "newsletter@example.com"
}
```

### whitelist_list

List all whitelisted senders.

### check_authentication

Verify Gmail API credentials are valid.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/app/data` | Directory for credentials, tokens, whitelist |
| `MCP_PORT` | `8000` | Port for SSE server |

## Data Files

Stored in `DATA_DIR`:

- `credentials.json` - Google OAuth client credentials (you provide)
- `token.json` - Gmail API access token (auto-generated)
- `whitelist.json` - List of trusted senders

## Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r src/requirements.txt

# Set environment
export DATA_DIR=./data

# Authenticate
python src/authenticate.py

# Run MCP server (stdio)
python src/server.py

# Or run with SSE
MCP_PORT=8000 python src/server.py
```

## Security Notes

- `credentials.json` and `token.json` contain sensitive data
- Never commit these files to version control
- The Docker setup mounts data as a volume, keeping it outside the image
- Unsubscribe actions require explicit confirmation
