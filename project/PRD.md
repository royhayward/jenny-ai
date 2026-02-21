# Product Requirements Document (PRD): Gmail Unsubscribe Manager

## 1. Introduction

This document outlines the requirements and high-level design for a suite of containerized command-line interface (CLI) tools, referred to as the "Gmail Unsubscribe Manager." This toolset aims to help users efficiently manage email subscriptions by identifying unsubscribe options within emails and automating the unsubscribe process, while also providing a whitelist mechanism for desired senders.

The tools will run within a Docker container to ensure portability, consistent execution environments, and simplified dependency management.

## 2. Goals

*   **Efficient Unsubscribe Identification:** Automatically scan emails for explicit unsubscribe links or instructions.
*   **Automated Unsubscription:** Provide a mechanism to act on identified unsubscribe information.
*   **Sender Whitelisting:** Allow users to define a whitelist of trusted senders whose emails should be excluded from unsubscribe recommendations.
*   **Containerized Deployment:** Ensure the tools can be easily deployed and run in a consistent environment using Docker.
*   **User Control & Safety:** Implement explicit user confirmation for any unsubscribe action to prevent accidental removals.

## 3. Features

### 3.1. Tool 1: `filter_emails.py` (Email Filtering and Unsubscribe Extraction)

**Description:** This tool searches the user's Gmail inbox based on specified criteria and extracts potential unsubscribe links or instructions from matching emails.

**Inputs (CLI Arguments):**
*   `--search-term <TERM>`: A keyword or phrase to search for within email subjects or bodies (e.g., "unsubscribe"). **(Required)**
*   `--status <unread|read|all>`: Filters emails by their read status. **(Required)**
*   `--timeframe <Xd|Xw|Xm>`: (Optional) Filters emails within a specific period (e.g., "30d" for last 30 days, "2w" for last 2 weeks, "1m" for last 1 month).
*   `--max-results <INT>`: (Optional) Maximum number of emails to process per execution (for pagination).
*   `--exclude-whitelisted`: (Optional Flag) If present, emails from senders in the whitelist will be excluded from the results.

**Functionality:**
*   Constructs and executes Gmail API queries using the provided inputs.
*   Fetches full message content (prioritizing HTML parts, falling back to plain text).
*   Parses email content to identify:
    *   Standard `List-Unsubscribe` headers.
    *   `<a href="...unsubscribe...">` links within HTML bodies.
    *   Common textual unsubscribe instructions using regex patterns.
*   Handles pagination for large result sets.

**Output:** A paginated list, for each matching email, containing:
*   Sender email address.
*   Email Subject line.
*   Extracted unsubscribe link or instructions.
*   Gmail `message_id` (for subsequent actions).
*   A summary count of all matching emails found.

### 3.2. Tool 2: `unsubscribe_action.py` (Unsubscribe Executor)

**Description:** This tool takes unsubscribe information extracted by `filter_emails.py` and attempts to perform the unsubscribe action.

**Inputs (CLI Arguments):**
*   `--unsubscribe-info <LINK_OR_INSTRUCTIONS>`: The unsubscribe link (URL) or textual instructions extracted from an email. **(Required)**
*   `--sender <EMAIL>`: (Optional) The sender's email address, primarily used for instruction-based unsubscriptions (e.g., "reply to this sender").
*   `--message-id <ID>`: (Optional) The Gmail `message_id` of the original email, used for post-unsubscribe actions.

**Functionality:**
*   **User Confirmation:** Prompts the user for explicit confirmation before executing any unsubscribe action.
*   **Link-based Unsubscribe:** If `unsubscribe-info` is a URL, performs an HTTP GET request to that URL.
*   **Instruction-based Unsubscribe:** If `unsubscribe-info` describes an action (e.g., "reply with UNSUBSCRIBE"):
    *   Attempts to parse the instructions to identify reply-to addresses and necessary subject/body content.
    *   Uses the Gmail API to draft and/or send a new email.
*   **Post-Unsubscribe Actions (Optional):** After successful unsubscribe, can optionally:
    *   Mark the original email (`message_id`) as `read` in Gmail.
    *   Move the original email to a custom "Unsubscribed" label (creates the label if it doesn't exist).

**Output:** Confirmation of action taken, or error messages.

### 3.3. Tool 3: `whitelist_manager.py` (Sender Whitelist Management)

**Description:** A utility to manage a list of trusted sender email addresses. Emails from whitelisted senders can be optionally ignored by `filter_emails.py`.

**Inputs (CLI Commands):**
*   `add <email_address>`: Adds the specified email address to the whitelist.
*   `remove <email_address>`: Removes the specified email address from the whitelist.
*   `list`: Displays all email addresses currently in the whitelist.

**Functionality:**
*   Stores and retrieves whitelisted email addresses from a persistent `whitelist.json` file.
*   Ensures unique entries in the whitelist.

**Output:** Confirmation of whitelist modifications or the current list of whitelisted senders.

## 4. Technical Architecture

### 4.1. Core Components

*   **Python Scripts:** Each tool (`authenticate.py`, `gmail_client.py`, `filter_emails.py`, `unsubscribe_action.py`, `whitelist_manager.py`) will be a separate Python script.
*   **Google API Client Library for Python:** Used for interacting with the Gmail API.
*   **`requests` library:** For making HTTP requests to unsubscribe links.
*   **`beautifulsoup4`:** For robust HTML parsing of email bodies to find unsubscribe information.
*   **`argparse`:** For building user-friendly command-line interfaces for each tool.

### 4.2. Containerization (Docker)

*   **Dockerfile:** Defines the build process for a Docker image:
    *   Base Image: `python:3.9-slim-buster` (or similar).
    *   Working Directory: `/app`.
    *   Dependency Installation: `pip install` from `requirements.txt`.
*   **Persistent Data:**
    *   `credentials.json`: Google OAuth 2.0 Client ID (provided by user, mounted into container).
    *   `token.json`: Google API refresh/access tokens (generated by `authenticate.py`, mounted into container).
    *   `whitelist.json`: List of whitelisted senders (managed by `whitelist_manager.py`, mounted into container).
    *   These files will be mounted as volumes during `docker run` commands to ensure persistence across container lifecycles and to keep sensitive data out of image layers.

### 4.3. Authentication Flow

1.  **Initial Setup:** User provides `credentials.json` on the host machine.
2.  **`authenticate.py` Execution:**
    *   Executed *once* inside the container with port forwarding (`-p 8080:8080`).
    *   Launches a local web server, redirects user to Google for authorization.
    *   Receives authorization callback, exchanges authorization code for tokens.
    *   Saves tokens (including refresh token) to `token.json` on the host machine (via volume mount).
3.  **Subsequent Operations:** `gmail_client.py` uses `token.json` to refresh access tokens non-interactively.

## 5. Directory Structure

```
gmail_tools/
├── src/
│   ├── authenticate.py
│   ├── gmail_client.py
│   ├── filter_emails.py
│   ├── unsubscribe_action.py
│   ├── whitelist_manager.py
│   └── requirements.txt
├── Dockerfile
├── README.md
├── credentials.json  (User-provided, will be mounted)
├── token.json        (Generated/managed by authenticate.py, will be mounted)
└── whitelist.json    (Managed by whitelist_manager.py, will be mounted)
```

## 6. Development Phases

**Phase 0: User Setup**
*   Create Google Cloud Project, enable Gmail API, download `credentials.json`.

**Phase 1: Project Structure & Containerization**
*   Create `gmail_tools` directory.
*   Define `requirements.txt`.
*   Create `Dockerfile`.

**Phase 2: Authentication & Gmail Client**
*   Implement `authenticate.py`.
*   Implement `gmail_client.py`.

**Phase 3: Email Filtering & Extraction**
*   Implement `filter_emails.py` with CLI arguments, Gmail API integration, and parsing logic.

**Phase 4: Unsubscribe Action**
*   Implement `unsubscribe_action.py` with CLI arguments, user confirmation, and action logic (HTTP GET, Gmail API send).

**Phase 5: Whitelist Management**
*   Implement `whitelist_manager.py` with CLI commands and JSON file persistence.

**Phase 6: Documentation & Testing**
*   Create comprehensive `README.md` with setup, build, run, and usage instructions.
*   Guide manual testing procedures for each tool.

## 7. Open Questions / Dependencies / Risks

*   **User Action for Google Cloud Setup:** Absolutely critical first step that must be performed by the user.
*   **Email Parsing Robustness:** Parsing unsubscribe instructions from varied email HTML/plain text content can be complex and may require ongoing refinement. Not all emails follow standard patterns.
*   **Instruction-based Unsubscribe Reliability:** Automatically drafting/sending emails based on parsed instructions (e.g., "reply with UNSUBSCRIBE") is inherently less reliable than clicking a direct link and relies heavily on accurate instruction parsing. User discretion and confirmation will be paramount.
*   **Network Access for Container:** The container will require outbound internet access to communicate with the Gmail API and unsubscribe links.
*   **User Experience (CLI):** Ensuring the CLI is intuitive and provides clear feedback for all operations.

---
