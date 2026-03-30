"""
Joseph WhatsApp Health Support Agent
--------------------------------------
Connects the Joseph health support agent to WhatsApp via Twilio.
Text the agent from your phone — it can document incidents, log communications,
summarize the case, and draft complaints, all saved to the folder system.

Setup:
    1. Create a free Twilio account at twilio.com
    2. Enable the WhatsApp Sandbox (Twilio Console > Messaging > Try it out > Send a WhatsApp message)
    3. Set environment variables (see .env.example)
    4. Run: python server.py
    5. Expose publicly with: ngrok http 5000
    6. Set the Twilio sandbox webhook URL to: https://your-ngrok-url.ngrok.io/whatsapp

Usage:
    Text your Twilio sandbox number from WhatsApp.
    The agent will respond as Joseph's health support advocate.
    Type "reset" to start a fresh conversation.
    Type "summary" for a quick case status update.
"""

import os
import json
import datetime
from pathlib import Path
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
import anthropic

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # joseph-support/
INCIDENTS_DIR   = BASE_DIR / "case-documentation" / "incidents"
COMMS_DIR       = BASE_DIR / "case-documentation" / "communications"
COMPLAINTS_DIR  = BASE_DIR / "legal-advocacy" / "complaint-letters"
RIGHTS_FILE     = BASE_DIR / "legal-advocacy" / "patient-rights" / "patient_rights_reference.md"
STANDARDS_FILE  = BASE_DIR / "resources" / "dialysis_care_standards.md"
CONTACTS_FILE   = BASE_DIR / "resources" / "reporting_contacts.md"
HISTORY_FILE    = Path(__file__).parent / "conversation_history.json"

# ── Config ─────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN", "")
VALIDATE_TWILIO_SIG = os.environ.get("VALIDATE_TWILIO_SIG", "true").lower() == "true"
MAX_HISTORY_TURNS   = 20   # keep last N user+assistant pairs per number
MAX_WHATSAPP_CHARS  = 1500 # split long responses into chunks

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Joseph's health support advocate, reachable via WhatsApp.
Joseph is a dialysis patient whose family is documenting potentially misappropriated
or substandard care and building a case for advocacy.

Your job is to help the user:
- Document incidents of concerning care
- Log communications with facility staff
- Review and summarize the case
- Understand patient rights and dialysis care standards
- Draft complaint letters
- Prepare questions for medical appointments

IMPORTANT FORMATTING RULES for WhatsApp:
- Keep responses concise and clear — this is a text conversation
- Use plain text, not markdown headers or tables
- Use short paragraphs and line breaks for readability
- Emoji are fine sparingly (✅ ⚠️ 📋 etc.)
- If a response would be very long, summarize and offer to go deeper
- When saving a file, confirm the filename so the user knows it was saved

CONVERSATION FLOW:
- On first message or after "reset", introduce yourself briefly and ask what they need
- Guide the user through documenting incidents with simple, focused questions — one at a time
- When you have enough info for a document, save it using the appropriate tool
- Be warm and supportive — this family is under stress

COMMANDS the user can type:
- "summary" → give a quick case status update
- "reset" → start fresh (history is cleared by the server before this reaches you)
- "help" → list what you can do

You are NOT a lawyer or doctor. Remind the user to consult professionals for legal decisions."""

# ── Tools ──────────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "save_incident_report",
        "description": "Save a structured incident report to the incidents folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date":                  {"type": "string", "description": "Date of incident (YYYY-MM-DD)"},
                "time":                  {"type": "string", "description": "Time (HH:MM AM/PM)"},
                "location":              {"type": "string", "description": "Where it occurred"},
                "summary":               {"type": "string", "description": "One-line summary"},
                "detailed_account":      {"type": "string", "description": "Full factual account"},
                "expected_care":         {"type": "string", "description": "What should have happened"},
                "actual_care":           {"type": "string", "description": "What actually happened"},
                "joseph_condition_before": {"type": "string"},
                "joseph_condition_after":  {"type": "string"},
                "staff_involved":        {"type": "string"},
                "witnesses":             {"type": "string"},
            },
            "required": ["date", "summary", "detailed_account"],
        },
    },
    {
        "name": "save_communication_log",
        "description": "Save a log of a communication with facility staff or other parties.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date":             {"type": "string"},
                "time":             {"type": "string"},
                "method":           {"type": "string", "description": "Phone / Email / In-Person / Letter"},
                "contact_name":     {"type": "string"},
                "contact_role":     {"type": "string"},
                "purpose":          {"type": "string"},
                "summary":          {"type": "string"},
                "commitments_made": {"type": "string"},
                "outcome":          {"type": "string"},
            },
            "required": ["date", "contact_name", "summary"],
        },
    },
    {
        "name": "draft_complaint_letter",
        "description": "Draft a formal complaint letter and save it to complaint-letters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient":          {"type": "string"},
                "subject":            {"type": "string"},
                "incidents_summary":  {"type": "string"},
                "desired_outcome":    {"type": "string"},
                "sender_name":        {"type": "string"},
                "sender_relationship":{"type": "string"},
            },
            "required": ["recipient", "subject", "incidents_summary"],
        },
    },
    {
        "name": "read_reference_file",
        "description": "Read patient rights, care standards, or contacts reference.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "enum": ["patient_rights", "care_standards", "contacts"],
                }
            },
            "required": ["file"],
        },
    },
    {
        "name": "list_and_summarize_incidents",
        "description": "List all saved incident reports and return a brief summary of each.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# ── Tool Handlers ──────────────────────────────────────────────────────────────

def _slug(text: str, maxlen: int = 35) -> str:
    return text.lower().replace(" ", "_")[:maxlen]

def save_incident_report(inp: dict) -> str:
    date = inp.get("date", datetime.date.today().isoformat())
    filename = f"{date}_incident_{_slug(inp.get('summary', 'incident'))}.md"
    path = INCIDENTS_DIR / filename
    content = f"""# Incident Report

**Date:** {date}
**Time:** {inp.get('time', 'Unknown')}
**Location:** {inp.get('location', 'Unknown')}

## Summary
{inp.get('summary', '')}

## Detailed Account
{inp.get('detailed_account', '')}

## Expected Care
{inp.get('expected_care', '(not specified)')}

## What Actually Happened
{inp.get('actual_care', '(not specified)')}

## Joseph Before
{inp.get('joseph_condition_before', '(not recorded)')}

## Joseph After
{inp.get('joseph_condition_after', '(not recorded)')}

## Staff Involved
{inp.get('staff_involved', '(unknown)')}

## Witnesses
{inp.get('witnesses', 'None identified')}

## Status
- [ ] Reported to facility
- [ ] Complaint filed

_Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_
"""
    path.write_text(content, encoding="utf-8")
    return f"Saved: {filename}"


def save_communication_log(inp: dict) -> str:
    date = inp.get("date", datetime.date.today().isoformat())
    filename = f"{date}_comm_{_slug(inp.get('contact_name', 'unknown'))}.md"
    path = COMMS_DIR / filename
    content = f"""# Communication Log

**Date:** {date}  **Time:** {inp.get('time', '')}
**Method:** {inp.get('method', '')}
**Contact:** {inp.get('contact_name', '')} — {inp.get('contact_role', '')}

## Purpose
{inp.get('purpose', '')}

## Summary
{inp.get('summary', '')}

## Commitments Made
{inp.get('commitments_made', 'None recorded')}

## Outcome
{inp.get('outcome', '')}

_Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_
"""
    path.write_text(content, encoding="utf-8")
    return f"Saved: {filename}"


def draft_complaint_letter(inp: dict) -> str:
    today = datetime.date.today().isoformat()
    filename = f"{today}_complaint_{_slug(inp.get('subject', 'complaint'))}.md"
    path = COMPLAINTS_DIR / filename
    sender = inp.get("sender_name", "[Family Member]")
    rel = inp.get("sender_relationship", "family member")
    content = f"""# Complaint Letter — DRAFT

**To:** {inp.get('recipient', '')}
**From:** {sender} ({rel} of Joseph)
**Date:** {today}
**Re:** {inp.get('subject', '')}

---

{today}

{inp.get('recipient', '')}
[Address]

RE: {inp.get('subject', '')}

Dear {inp.get('recipient', '')},

I am writing to formally raise concerns regarding the care provided to my {rel},
Joseph, at your facility.

## Summary of Concerns

{inp.get('incidents_summary', '')}

## Impact on Joseph

These incidents have caused Joseph unnecessary physical and emotional distress and
appear to represent a departure from standards required under 42 CFR § 494.70.

## Requested Resolution

{inp.get('desired_outcome', 'We request a written response within 14 days and a meeting with the Medical Director.')}

We expect a written response within **14 days**. If unresolved, we are prepared to
escalate to the ESRD Network, State Survey Agency, and CMS.

Sincerely,

{sender}
{rel} of Joseph
[Phone] [Email]

---
_Draft — review before sending. Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_
"""
    path.write_text(content, encoding="utf-8")
    return f"Saved draft: {filename}"


def read_reference_file(inp: dict) -> str:
    mapping = {
        "patient_rights": RIGHTS_FILE,
        "care_standards": STANDARDS_FILE,
        "contacts": CONTACTS_FILE,
    }
    p = mapping.get(inp.get("file", ""))
    if p and p.exists():
        return p.read_text(encoding="utf-8")
    return "File not found."


def list_and_summarize_incidents(_: dict) -> str:
    files = sorted(
        f for f in INCIDENTS_DIR.glob("*.md") if not f.name.startswith("TEMPLATE")
    )
    if not files:
        return "No incidents documented yet."
    lines = [f"Found {len(files)} incident(s):"]
    for f in files:
        text = f.read_text(encoding="utf-8")
        summary_line = next(
            (ln.strip() for ln in text.splitlines()
             if ln.strip() and not ln.startswith("#") and not ln.startswith("**") and not ln.startswith("_")),
            f.name
        )
        lines.append(f"• {f.name}: {summary_line[:100]}")
    return "\n".join(lines)


TOOL_HANDLERS = {
    "save_incident_report":      save_incident_report,
    "save_communication_log":    save_communication_log,
    "draft_complaint_letter":    draft_complaint_letter,
    "read_reference_file":       read_reference_file,
    "list_and_summarize_incidents": list_and_summarize_incidents,
}

# ── Conversation History ───────────────────────────────────────────────────────

def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_history(store: dict) -> None:
    HISTORY_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")

def get_user_history(store: dict, phone: str) -> list:
    return store.get(phone, [])

def set_user_history(store: dict, phone: str, history: list) -> None:
    # Trim to last MAX_HISTORY_TURNS turns
    if len(history) > MAX_HISTORY_TURNS * 2:
        history = history[-(MAX_HISTORY_TURNS * 2):]
    store[phone] = history
    save_history(store)

# ── Claude Agentic Loop ────────────────────────────────────────────────────────

def run_claude(history: list, user_message: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = history + [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        # Collect any text to return
        text_parts = [b.text for b in response.content if hasattr(b, "text") and b.text]

        if response.stop_reason != "tool_use":
            return "\n".join(text_parts).strip(), messages

        # Execute tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    result = handler(block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    result = f"Tool error: {e}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})


# ── WhatsApp Message Splitting ─────────────────────────────────────────────────

def split_message(text: str, max_len: int = MAX_WHATSAPP_CHARS) -> list[str]:
    """Split a long response into WhatsApp-sized chunks at paragraph boundaries."""
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_len:
            if current:
                chunks.append(current.strip())
            current = paragraph
        else:
            current = (current + "\n\n" + paragraph).strip() if current else paragraph
    if current:
        chunks.append(current.strip())
    return chunks or [text[:max_len]]


# ── Flask App ──────────────────────────────────────────────────────────────────

app = Flask(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # Optional Twilio signature validation
    if VALIDATE_TWILIO_SIG and TWILIO_AUTH_TOKEN:
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        url = request.url
        params = request.form.to_dict()
        sig = request.headers.get("X-Twilio-Signature", "")
        if not validator.validate(url, params, sig):
            return Response("Forbidden", status=403)

    incoming = request.form.get("Body", "").strip()
    sender   = request.form.get("From", "unknown")  # e.g. "whatsapp:+15551234567"

    store   = load_history()
    history = get_user_history(store, sender)

    # Handle special commands
    if incoming.lower() == "reset":
        set_user_history(store, sender, [])
        resp = MessagingResponse()
        resp.message("Conversation reset. Hi again — I'm Joseph's health support assistant. What do you need help with?")
        return str(resp)

    try:
        reply, updated_history = run_claude(history, incoming)
    except Exception as e:
        reply = f"Sorry, something went wrong: {e}\n\nTry typing 'reset' to start fresh."
        updated_history = history

    # Save updated history (strip tool_result turns to save space)
    clean_history = [
        m for m in updated_history
        if not (isinstance(m.get("content"), list) and
                any(isinstance(b, dict) and b.get("type") == "tool_result" for b in m["content"]))
    ]
    set_user_history(store, sender, clean_history)

    # Build Twilio response — split if needed
    twiml = MessagingResponse()
    for chunk in split_message(reply):
        twiml.message(chunk)

    return str(twiml)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "incidents": len(list(INCIDENTS_DIR.glob("*.md")))}


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        exit(1)
    print("Joseph WhatsApp Agent starting on port 5000...")
    print(f"Incidents folder: {INCIDENTS_DIR}")
    app.run(host="0.0.0.0", port=5000, debug=False)
