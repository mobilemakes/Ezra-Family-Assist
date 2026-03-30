"""
Joseph Health Support Agent
----------------------------
A Claude-powered conversational agent to help the family document incidents,
understand patient rights, draft complaints, and build a case around Joseph's care.

Usage:
    python health_support_agent.py

Requirements:
    pip install -r requirements.txt

Set your Anthropic API key:
    export ANTHROPIC_API_KEY=your_key_here
"""

import os
import sys
import json
import datetime
from pathlib import Path

import anthropic

# ── Paths ──────────────────────────────────────────────────────────────────────
AGENT_DIR = Path(__file__).parent
JOSEPH_DIR = AGENT_DIR.parent
INCIDENTS_DIR = JOSEPH_DIR / "case-documentation" / "incidents"
APPOINTMENTS_DIR = JOSEPH_DIR / "case-documentation" / "appointments"
COMMUNICATIONS_DIR = JOSEPH_DIR / "case-documentation" / "communications"
SESSIONS_DIR = JOSEPH_DIR / "medical-records" / "dialysis-sessions"
COMPLAINTS_DIR = JOSEPH_DIR / "legal-advocacy" / "complaint-letters"
PATIENT_RIGHTS_FILE = JOSEPH_DIR / "legal-advocacy" / "patient-rights" / "patient_rights_reference.md"
CARE_STANDARDS_FILE = JOSEPH_DIR / "resources" / "dialysis_care_standards.md"
CONTACTS_FILE = JOSEPH_DIR / "resources" / "reporting_contacts.md"

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a compassionate and knowledgeable health advocacy assistant helping a family
support Joseph, a dialysis patient who may be receiving misappropriated or substandard care.

Your role is to:
1. Help the family document incidents of concerning care clearly and factually.
2. Explain patient rights under federal ESRD regulations (42 CFR § 494.70), HIPAA, and state laws.
3. Help identify whether described situations constitute substandard or improper care.
4. Draft formal complaint letters to facilities, ESRD Networks, CMS, or state agencies.
5. Suggest questions to ask at medical appointments.
6. Provide emotional support and reassurance while keeping the family focused and organized.
7. Summarize the case and help identify patterns across documented incidents.

Important guidelines:
- Always be calm, clear, and supportive.
- Be factual and evidence-focused when helping document incidents.
- Clearly distinguish between what is documented/known versus what is suspected.
- Remind the family that you are an AI and that consulting a patient advocate, healthcare attorney,
  or social worker is important for legal matters.
- Do not provide specific medical advice or diagnoses.
- When drafting complaint letters, use professional, factual language and cite relevant regulations.
- When the user shares an incident, help them structure it: who, what, when, where, expected care vs actual care.

You have access to the following context files that can be read for reference:
- Patient Rights Reference
- Dialysis Care Standards
- Reporting Contacts

When the user asks about rights, standards, or who to contact, draw on this knowledge accurately.
"""

# ── Tool Definitions ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "save_incident_report",
        "description": (
            "Save a structured incident report to the incidents folder. "
            "Call this after gathering enough details about a concerning event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date of incident (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Time of incident (HH:MM AM/PM)"},
                "location": {"type": "string", "description": "Where the incident occurred"},
                "summary": {"type": "string", "description": "Brief one-line summary"},
                "detailed_account": {"type": "string", "description": "Full factual account of what happened"},
                "expected_care": {"type": "string", "description": "What care should have been provided"},
                "actual_care": {"type": "string", "description": "What actually happened"},
                "joseph_condition_before": {"type": "string", "description": "Joseph's condition before the incident"},
                "joseph_condition_after": {"type": "string", "description": "Joseph's condition after the incident"},
                "staff_involved": {"type": "string", "description": "Names or roles of staff involved"},
                "witnesses": {"type": "string", "description": "Any witnesses present"},
            },
            "required": ["date", "summary", "detailed_account"],
        },
    },
    {
        "name": "save_communication_log",
        "description": "Save a log of a communication (phone call, email, in-person conversation) with facility staff or other parties.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Time (HH:MM AM/PM)"},
                "method": {"type": "string", "description": "Phone / Email / In-Person / Letter"},
                "contact_name": {"type": "string", "description": "Name of person contacted"},
                "contact_role": {"type": "string", "description": "Their role / title"},
                "purpose": {"type": "string", "description": "Why the communication happened"},
                "summary": {"type": "string", "description": "What was discussed"},
                "commitments_made": {"type": "string", "description": "Any commitments made by either party"},
                "outcome": {"type": "string", "description": "Result of the communication"},
            },
            "required": ["date", "contact_name", "summary"],
        },
    },
    {
        "name": "draft_complaint_letter",
        "description": "Draft a formal complaint letter and save it to the complaint-letters folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Who the letter is addressed to (e.g., Facility Administrator, ESRD Network)"},
                "subject": {"type": "string", "description": "Subject line of the complaint"},
                "incidents_summary": {"type": "string", "description": "Summary of the incidents being complained about"},
                "desired_outcome": {"type": "string", "description": "What resolution the family is seeking"},
                "sender_name": {"type": "string", "description": "Name of the family member writing"},
                "sender_relationship": {"type": "string", "description": "Relationship to Joseph"},
            },
            "required": ["recipient", "subject", "incidents_summary"],
        },
    },
    {
        "name": "read_reference_file",
        "description": "Read a reference file (patient rights, care standards, or contacts) to answer a question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "enum": ["patient_rights", "care_standards", "contacts"],
                    "description": "Which reference file to read",
                }
            },
            "required": ["file"],
        },
    },
    {
        "name": "list_documented_incidents",
        "description": "List all incident reports that have been saved so far.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "summarize_case",
        "description": "Summarize the current state of Joseph's documented case by reviewing all saved incident reports.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# ── Tool Handlers ──────────────────────────────────────────────────────────────

def save_incident_report(inputs: dict) -> str:
    date = inputs.get("date", datetime.date.today().isoformat())
    slug = inputs.get("summary", "incident").lower().replace(" ", "_")[:40]
    filename = f"{date}_incident_{slug}.md"
    filepath = INCIDENTS_DIR / filename

    content = f"""# Incident Report

**Date:** {date}
**Time:** {inputs.get('time', 'Unknown')}
**Location:** {inputs.get('location', 'Unknown')}
**Reported By:** (family member)

---

## Summary of Incident

{inputs.get('summary', '')}

---

## Detailed Account

{inputs.get('detailed_account', '')}

---

## What Care Was Expected?

{inputs.get('expected_care', '(not specified)')}

---

## What Actually Happened?

{inputs.get('actual_care', '(not specified)')}

---

## Joseph's Condition Before the Incident

{inputs.get('joseph_condition_before', '(not recorded)')}

---

## Joseph's Condition After the Incident

{inputs.get('joseph_condition_after', '(not recorded)')}

---

## Staff Involved

{inputs.get('staff_involved', '(unknown)')}

---

## Witnesses

{inputs.get('witnesses', 'None identified')}

---

## Status

- [ ] Reported to facility management
- [ ] Complaint filed with oversight body
- [ ] Legal consultation sought

---

_Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_
"""
    filepath.write_text(content, encoding="utf-8")
    return f"Incident report saved: {filepath.name}"


def save_communication_log(inputs: dict) -> str:
    date = inputs.get("date", datetime.date.today().isoformat())
    contact = inputs.get("contact_name", "unknown").lower().replace(" ", "_")[:30]
    filename = f"{date}_comm_{contact}.md"
    filepath = COMMUNICATIONS_DIR / filename

    content = f"""# Communication Log

**Date:** {date}
**Time:** {inputs.get('time', 'Unknown')}
**Method:** {inputs.get('method', 'Unknown')}
**Contact:** {inputs.get('contact_name', '')} — {inputs.get('contact_role', '')}

---

## Purpose

{inputs.get('purpose', '(not specified)')}

---

## Summary

{inputs.get('summary', '')}

---

## Commitments Made

{inputs.get('commitments_made', 'None recorded')}

---

## Outcome

{inputs.get('outcome', '(not recorded)')}

---

_Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_
"""
    filepath.write_text(content, encoding="utf-8")
    return f"Communication log saved: {filepath.name}"


def draft_complaint_letter(inputs: dict) -> str:
    today = datetime.date.today().isoformat()
    recipient = inputs.get("recipient", "Facility Administrator")
    subject = inputs.get("subject", "Patient Care Complaint")
    slug = subject.lower().replace(" ", "_")[:40]
    filename = f"{today}_complaint_{slug}.md"
    filepath = COMPLAINTS_DIR / filename

    sender_name = inputs.get("sender_name", "[Family Member Name]")
    sender_relationship = inputs.get("sender_relationship", "family member")

    content = f"""# Complaint Letter — DRAFT

**To:** {recipient}
**From:** {sender_name} ({sender_relationship} of Joseph)
**Date:** {today}
**Re:** {subject}

---

{today}

{recipient}
[Facility / Organization Address]

**RE: {subject}**

Dear {recipient},

I am writing to formally raise concerns regarding the care provided to my {sender_relationship}, Joseph,
at your facility. I am his {sender_relationship} and am actively involved in his care.

## Summary of Concerns

{inputs.get('incidents_summary', '[Insert summary of incidents here]')}

## Impact on Joseph

The above incidents have caused Joseph unnecessary physical and emotional distress. We believe these
situations represent a departure from the standards of care required under 42 CFR § 494.70 (ESRD
Conditions for Coverage) and the rights afforded to patients receiving dialysis treatment.

## Requested Resolution

{inputs.get('desired_outcome', 'We request a formal written response within 14 days, a full review of Joseph\'s care, and a meeting with the Medical Director and Facility Administrator to discuss steps to prevent recurrence.')}

## Documentation

We have documented these incidents in detail, including dates, times, staff involved, and observed
conditions. This documentation is available upon request.

We expect a written response to this complaint within **14 days**. If we do not receive a satisfactory
response, we are prepared to escalate this matter to the ESRD Network, State Survey Agency, and the
Centers for Medicare & Medicaid Services (CMS).

Sincerely,

{sender_name}
{sender_relationship} of Joseph
[Phone Number]
[Email Address]

---

_Draft created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — Review before sending_
"""
    filepath.write_text(content, encoding="utf-8")
    return f"Complaint letter draft saved: {filepath.name}"


def read_reference_file(inputs: dict) -> str:
    file_map = {
        "patient_rights": PATIENT_RIGHTS_FILE,
        "care_standards": CARE_STANDARDS_FILE,
        "contacts": CONTACTS_FILE,
    }
    path = file_map.get(inputs["file"])
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return "Reference file not found."


def list_documented_incidents(inputs: dict) -> str:
    files = sorted(INCIDENTS_DIR.glob("*.md"))
    files = [f for f in files if not f.name.startswith("TEMPLATE")]
    if not files:
        return "No incident reports documented yet."
    return "Documented incidents:\n" + "\n".join(f"- {f.name}" for f in files)


def summarize_case(inputs: dict) -> str:
    files = sorted(INCIDENTS_DIR.glob("*.md"))
    files = [f for f in files if not f.name.startswith("TEMPLATE")]
    if not files:
        return "No incidents documented yet. Start by describing a concerning event."
    summaries = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        # Extract the summary line
        for line in text.splitlines():
            if line.strip() and not line.startswith("#") and not line.startswith("**") and not line.startswith("_"):
                summaries.append(f"[{f.name}]: {line.strip()[:120]}")
                break
    return f"Case summary — {len(files)} incident(s) documented:\n\n" + "\n".join(summaries)


TOOL_HANDLERS = {
    "save_incident_report": save_incident_report,
    "save_communication_log": save_communication_log,
    "draft_complaint_letter": draft_complaint_letter,
    "read_reference_file": read_reference_file,
    "list_documented_incidents": list_documented_incidents,
    "summarize_case": summarize_case,
}

# ── Agent Loop ─────────────────────────────────────────────────────────────────

def run_agent():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("Run: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    conversation_history = []

    print("=" * 60)
    print("  Joseph Health Support Agent")
    print("=" * 60)
    print("I'm here to help you document Joseph's care, understand")
    print("his rights, and build a case if needed.")
    print()
    print("You can ask me to:")
    print("  - Document an incident")
    print("  - Log a communication with facility staff")
    print("  - Explain patient rights or care standards")
    print("  - Draft a complaint letter")
    print("  - Summarize the documented case so far")
    print("  - Suggest questions for appointments")
    print()
    print("Type 'quit' or 'exit' to end the session.")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended. Stay strong — Joseph has great support.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print("\nSession saved. Take care.")
            break

        conversation_history.append({"role": "user", "content": user_input})

        # Agentic loop — keep going until no more tool calls
        while True:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=conversation_history,
            )

            # Collect all text and tool use blocks
            assistant_content = response.content
            conversation_history.append({"role": "assistant", "content": assistant_content})

            # Print any text blocks
            for block in assistant_content:
                if block.type == "text" and block.text.strip():
                    print(f"\nAgent: {block.text}\n")

            # If no tool use, we're done with this turn
            if response.stop_reason != "tool_use":
                break

            # Process tool calls
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    print(f"  [Using tool: {tool_name}]")
                    handler = TOOL_HANDLERS.get(tool_name)
                    if handler:
                        try:
                            result = handler(tool_input)
                        except Exception as e:
                            result = f"Error running tool: {e}"
                    else:
                        result = f"Unknown tool: {tool_name}"
                    print(f"  -> {result}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Feed tool results back
            conversation_history.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    run_agent()
