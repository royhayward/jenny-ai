# Product Requirements Document (PRD): Gmail Unsubscribe Manager

## 1. Introduction

This document outlines the requirements and high-level design for the "Gmail Unsubscribe Manager," an MCP (Model Context Protocol) server that helps users efficiently manage email subscriptions by identifying unsubscribe options within emails and automating the unsubscribe process, while also providing a whitelist mechanism for desired senders.

The server runs within a Docker container to ensure portability, consistent execution environments, and simplified dependency management. It can be integrated with MCP clients like opencode, Claude Desktop, or other AI assistants.

## 2. Goals

*   **Efficient Unsubscribe Identification:** Automatically scan emails for explicit unsubscribe links or instructions.
*   **Automated Unsubscription:** Provide a mechanism to act on identified unsubscribe information.
*   **Sender Whitelisting:** Allow users to define a whitelist of trusted senders whose emails should be excluded from unsubscribe recommendations.
*   **Containerized Deployment:** Ensure the tools can be easily deployed and run in a consistent environment using Docker.
*   **User Control & Safety:** Implement explicit confirmation for any unsubscribe action to prevent accidental removals.
*   **MCP Integration:** Enable AI assistants to interact with Gmail for subscription management through standardized MCP tools.

## 3. Features

### 3.1. MCP Tool: `filter_emails` (Email Filtering and Unsubscribe Extraction)

**Description:** Searches the user's Gmail inbox based on specified criteria and extracts potential unsubscribe links or instructions from matching emails.

**Parameters:**
*   `search_term` (string, required): A keyword or phrase to search for within email subjects or bodies (e.g., "unsubscribe").
*   `status` (string, default: "all"): Filters emails by read status - "unread", "read", or "all".
*   `timeframe` (string, default: "30d"): Filters emails within a specific period (e.g., "30d" for last 30 days, "2w" for last 2 weeks, "1m" for last 1 month).
*   `max_results` (integer, default: 50): Maximum number of emails to process.
*   `exclude_whitelisted` (boolean, default: true): If true, emails from whitelisted senders will be excluded.

**Functionality:**
*   Constructs and executes Gmail API queries using the provided inputs.
*   Fetches full message content (prioritizing HTML parts, falling back to plain text).
*   Parses email content to identify:
    *   Standard `List-Unsubscribe` headers.
    *   `<a href="...unsubscribe...">` links within HTML bodies.
    *   Common textual unsubscribe instructions using regex patterns.
*   Handles pagination for large result sets.

**Output:** JSON containing:
*   Total count of matching emails.
*   For each email: sender, subject, message_id, and extracted unsubscribe options.

### 3.2. MCP Tool: `unsubscribe_action` (Unsubscribe Executor)

**Description:** Takes unsubscribe information and attempts to perform the unsubscribe action.

**Parameters:**
*   `unsubscribe_info` (string, required): The unsubscribe link (URL) or textual instructions.
*   `action_type` (string, default: "link"): Type of action - "link" (HTTP GET) or "instruction" (send email).
*   `sender` (string, optional): Sender's email address for instruction-based unsubscriptions.
*   `message_id` (string, optional): Gmail message_id for post-unsubscribe actions.
*   `confirm` (boolean, default: false): Must be set to true to execute the action.

**Functionality:**
*   **Preview Mode:** If `confirm=false`, returns a preview without executing.
*   **Link-based Unsubscribe:** If `action_type="link"`, performs an HTTP GET request to the URL.
*   **Instruction-based Unsubscribe:** If `action_type="instruction"`, uses Gmail API to send an unsubscribe email.
*   **Post-Unsubscribe Actions:** After successful unsubscribe:
    *   Marks the original email as read.
    *   Adds "Unsubscribed" label (creates if doesn't exist).

**Output:** JSON with success status, HTTP response details, and any post-action results.

### 3.3. MCP Tools: Whitelist Management

#### `whitelist_add`
Add an email address to the whitelist.

**Parameters:**
*   `email_address` (string, required): Email address to whitelist.

**Output:** JSON with status and total whitelist count.

#### `whitelist_remove`
Remove an email address from the whitelist.

**Parameters:**
*   `email_address` (string, required): Email address to remove.

**Output:** JSON with status and total whitelist count.

#### `whitelist_list`
List all whitelisted email addresses.

**Output:** JSON with count and array of whitelisted emails.

### 3.4. MCP Tool: `check_authentication`

**Description:** Verifies Gmail API credentials are valid.

**Output:** JSON with authentication status and any error messages.

## 4. Technical Architecture

### 4.1. Core Components

*   **MCP Server (`server.py`):** FastMCP-based server exposing all tools via MCP protocol. Supports both stdio and SSE transports.
*   **Authentication (`authenticate.py`):** Handles OAuth 2.0 flow for initial Gmail API authorization.
*   **Gmail Client (`gmail_client.py`):** Standalone module for Gmail service initialization (available but server.py has its own implementation).
*   **Google API Client Library for Python:** Used for interacting with the Gmail API.
*   **FastMCP:** Framework for building MCP servers with minimal boilerplate.
*   **`requests` library:** For making HTTP requests to unsubscribe links.
*   **`beautifulsoup4`:** For robust HTML parsing of email bodies.

### 4.2. Containerization (Docker)

*   **Dockerfile:** Defines the build process for a Docker image with Python 3.x.
*   **docker-compose.yml:** Simplified container orchestration with volume mounts.
*   **Persistent Data (mounted volumes):**
    *   `credentials.json`: Google OAuth 2.0 Client ID (user-provided).
    *   `token.json`: Gmail API access/refresh tokens (auto-generated).
    *   `whitelist.json`: List of whitelisted senders (managed by tools).

### 4.3. Authentication Flow

1.  **Initial Setup:** User provides `credentials.json` in `email_service/data/`.
2.  **`authenticate.py` Execution:**
    *   Run once with port forwarding: `docker compose run --rm -p 8080:8080 email-service python src/authenticate.py`
    *   Launches local web server, redirects to Google OAuth consent.
    *   Saves tokens to `token.json` via volume mount.
3.  **Subsequent Operations:** Server automatically refreshes tokens using stored refresh token.

### 4.4. MCP Integration

The server can be integrated with MCP clients:

**SSE Transport (Docker):**
```json
{
  "mcpServers": {
    "email-service": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

**Stdio Transport (Local):**
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

## 5. Directory Structure

```
project-root/
├── project/
│   └── PRD.md               # This document
├── email_service/
│   ├── src/
│   │   ├── authenticate.py  # OAuth 2.0 authentication flow
│   │   ├── gmail_client.py  # Gmail service helper (standalone)
│   │   ├── server.py        # MCP server with all tools
│   │   └── requirements.txt # Python dependencies
│   ├── data/
│   │   ├── credentials.json # Google OAuth credentials (user-provided)
│   │   ├── token.json       # Gmail API tokens (auto-generated)
│   │   └── whitelist.json   # Whitelisted senders (managed)
│   └── README.md
├── Dockerfile
├── docker-compose.yml
└── .env
```

## 6. Development Phases

**Phase 0: User Setup**
*   Create Google Cloud Project, enable Gmail API, download `credentials.json`.

**Phase 1: Project Structure & Containerization** ✓ COMPLETE
*   Create `gmail_tools` directory.
*   Define `requirements.txt`.
*   Create `Dockerfile` and `docker-compose.yml`.

**Phase 2: Authentication & Gmail Client** ✓ COMPLETE
*   Implement `authenticate.py` with OAuth 2.0 flow.
*   Implement `gmail_client.py` as standalone module.

**Phase 3: MCP Server Implementation** ✓ COMPLETE
*   Implement `server.py` with FastMCP.
*   Implement `filter_emails` tool with Gmail API integration and parsing logic.
*   Implement `unsubscribe_action` tool with confirmation, HTTP GET, and email sending.
*   Implement whitelist tools (`add`, `remove`, `list`).
*   Implement `check_authentication` tool.

**Phase 4: Documentation** ✓ COMPLETE
*   Create comprehensive `README.md` with setup, build, run, and usage instructions.
*   Document MCP integration for opencode and other clients.

**Phase 5: Future Enhancements**
*   Additional unsubscribe instruction patterns.
*   Batch unsubscribe operations.
*   Email categorization suggestions.

## 7. Open Questions / Dependencies / Risks

*   **User Action for Google Cloud Setup:** Critical first step that must be performed by the user.
*   **Email Parsing Robustness:** Parsing unsubscribe instructions from varied email HTML/plain text content can be complex. Not all emails follow standard patterns.
*   **Instruction-based Unsubscribe Reliability:** Automatically drafting/sending emails based on parsed instructions is less reliable than direct link clicks.
*   **Network Access for Container:** Requires outbound internet access for Gmail API and unsubscribe links.
*   **MCP Client Compatibility:** Server tested with opencode; other MCP clients may have different requirements.

---
