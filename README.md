# HomeFix AI

**HomeFix AI** is a Hebrew-first, AI-powered home-appliance support assistant.
Users describe a household problem (TV, air conditioner, washing machine,
refrigerator, router, etc.) — optionally with a photo — and the assistant
walks them through troubleshooting using manufacturer manuals as grounding
knowledge, opens and tracks support cases, and can schedule reminders to
follow up later.

This repository contains the **Streamlit frontend**. All business logic,
AI orchestration, database access, and reminder/case actions live in the
n8n backend and are intentionally not part of this repo.

## Main Features

- Conversational, RTL Hebrew troubleshooting chat.
- Clarifying questions before diagnosis, so the assistant asks for missing
  details (device model, symptom) instead of guessing.
- Image upload with Gemini Vision analysis for visual symptoms (error codes,
  display issues, physical damage).
- Manufacturer-manual grounded answers (RAG) instead of generic advice.
- One-click case actions: mark a case resolved (**הסתדר**), continue
  troubleshooting (**עדיין לא הסתדר**), or set a reminder to check back later.
- Case and reminder management: list open cases/reminders, continue a case,
  close a case, update or complete a reminder.
- Quick-action shortcuts on the home screen and sidebar for common flows.
- Session-scoped conversation history in the sidebar.

## Architecture Overview

```
┌────────────────┐      multipart/form-data      ┌──────────────┐
│  Streamlit UI   │ ─────────────────────────────▶ │  n8n          │
│  (this repo)    │ ◀───────────────────────────── │  Workflow 1   │
└────────────────┘         JSON response           │  (HomeFix Main)│
                                                     └──────┬───────┘
                                                            │
                                     ┌──────────────────────┼───────────────────────┐
                                     ▼                      ▼                       ▼
                              ┌────────────┐        ┌──────────────┐        ┌──────────────┐
                              │  Supabase   │        │  Google      │        │  MCP server   │
                              │  (DB +      │        │  Gemini      │        │  (case /      │
                              │  vector RAG)│        │  (chat +     │        │  reminder     │
                              │             │        │  vision)     │        │  actions)     │
                              └────────────┘        └──────────────┘        └──────────────┘
```

The frontend talks **only** to a single n8n webhook (Workflow 1). It never
calls Supabase, Gemini, or the MCP server directly — all of that is
orchestrated server-side, which keeps API keys and infrastructure details
out of the client entirely.

## Technologies

- **Streamlit** — Python web UI framework (this frontend).
- **Python** — frontend application logic.
- **n8n** — backend workflow orchestration and API layer.
- **Supabase** — Postgres database (cases, reminders) and vector store
  (manufacturer manuals) with pgvector.
- **Google Gemini** — conversational AI, clarification logic, and image
  (vision) analysis.
- **RAG (Retrieval-Augmented Generation)** — manufacturer manuals are
  chunked, embedded, and retrieved to ground troubleshooting answers in
  real documentation rather than model guesswork.
- **MCP (Model Context Protocol)** — used by the backend to expose case and
  reminder actions (create, list, close, update) as callable tools.

## Main User Flow

1. User opens the app and either picks a quick-start category (TV, AC,
   other) or types a free-text description of the problem.
2. The assistant may ask a clarifying question (device model, symptom
   details) before diagnosing.
3. The assistant retrieves relevant sections from manufacturer manuals
   (RAG) and gives step-by-step troubleshooting guidance.
4. The user can attach a photo at any point; Gemini Vision analyzes it as
   part of the same conversation.
5. After a suggestion, the user responds with **הסתדר** (resolved),
   **עדיין לא הסתדר** (still broken, continue), or asks to be reminded
   later.
6. Resolving a case closes it in the backend; the user can immediately
   start a new issue.

## Case Management

Every troubleshooting conversation is tracked as a case in the backend.
From the sidebar, a user can list open cases, continue treatment on a
specific case by number, or close a case directly — all without leaving
the chat.

## Reminders

Reminders let a user ask to be checked in on later (e.g., "remind me
tomorrow if the issue is resolved"). Creating or managing a reminder
requires an email address, which the app collects once via a dialog and
reuses for the rest of the session. Reminders can be listed, rescheduled,
or marked complete from the sidebar.

## Image / Vision Support

The chat input accepts an optional image (JPG/PNG, up to 10 MB) alongside
free text. Images are sent to the backend together with the message and
analyzed by Gemini Vision as part of the same troubleshooting flow — no
separate upload step or endpoint.

## Manufacturer-Manual RAG

`manifest.json` and `documents/` contain the manufacturer manual pack used
to seed the Supabase vector store: PDF manuals across categories such as
TVs, air conditioners, washing machines, dryers, dishwashers,
refrigerators, ovens, and networking equipment, each tagged with
manufacturer, model family, and topic metadata. `upload_manual.py` is a
one-off ingestion script (not part of the running app) used to push these
documents into the backend's RAG pipeline.

## Project Structure

```
app.py                          Streamlit entry point: views, sidebar, chat
homefix_api.py                  Single function that calls the n8n webhook
homefix_ui.py                   RTL/CSS styling, Hebrew labels, ID parsing
requirements.txt                Python dependencies
README.md                       This file
.streamlit/
  config.toml                   Theme configuration
  secrets.toml                  Local secrets (git-ignored, not committed)
  secrets.toml.example          Placeholder template for secrets.toml
upload_manual.py                One-off RAG manual ingestion script
manifest.json                   Manufacturer-manual metadata for RAG seeding
documents/                      Manufacturer manual PDFs, grouped by category
```

## Local Setup

1. Open a terminal in the project folder.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create your local secrets file from the template:
   ```
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml
   ```
   (macOS/Linux: `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`)
4. Edit `.streamlit/secrets.toml` and set the required secret:
   ```toml
   N8N_WEBHOOK_URL = "https://YOUR-N8N-DOMAIN/webhook/YOUR-PRODUCTION-WEBHOOK"
   ```
5. Run the app:
   ```
   python -m streamlit run app.py
   ```

`.streamlit/secrets.toml` is git-ignored and must never be committed —
only `.streamlit/secrets.toml.example` (placeholders only) is tracked.

## Required Streamlit Secret

| Key | Description |
|---|---|
| `N8N_WEBHOOK_URL` | Production n8n Workflow 1 webhook URL. Never hardcoded in source; read exclusively via `st.secrets`. |

## Deployment Notes (Streamlit Community Cloud)

1. Push this repository to GitHub (`.streamlit/secrets.toml` will not be
   included — it's git-ignored).
2. In Streamlit Community Cloud, create a new app pointing at this repo
   with **`app.py`** as the entry point.
3. Under **App settings → Secrets**, add:
   ```toml
   N8N_WEBHOOK_URL = "https://YOUR-N8N-DOMAIN/webhook/YOUR-PRODUCTION-WEBHOOK"
   ```
4. Deploy. No other configuration, local paths, or environment-specific
   setup is required — the app has no local-only dependencies.

## Known Limitations / Future Improvements

- **Cross-session case/reminder history** — conversation history is
  currently frontend-only and session-scoped (kept in
  `st.session_state`); it does not persist across browser reloads or
  devices. A future iteration could key case/reminder lookups by user
  email/identity server-side so history survives across sessions.
- **More manufacturer manuals** — the current RAG pack covers a
  representative set of manufacturers/categories; expanding manual
  coverage would improve troubleshooting accuracy for more devices.
- **Better conversation-history persistence** — moving conversation
  storage into Supabase (rather than the local session cache) would allow
  users to resume past conversations after closing the browser.
- **Performance / latency optimization** — Gemini response time and RAG
  retrieval latency can be further optimized for a snappier chat
  experience under load.

## Notes

- All quick-action buttons (case/reminder actions, resolved/continue/remind
  follow-ups, sidebar navigation) build a natural-language Hebrew message
  and send it through the same webhook as free-text chat — the AI routing
  in Workflow 1 remains the single source of truth for what actually
  happens in the backend.
- Internal backend status values are never shown to the user; they are
  translated to Hebrew labels before display.
