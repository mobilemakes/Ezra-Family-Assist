# Joseph Health Support System

A documentation and advocacy toolkit for Joseph, who is receiving dialysis care. This system helps track treatment, log incidents of potentially misappropriated care, and build a case for advocacy or formal complaints.

## Folder Structure

```
joseph-support/
├── agent/                        # AI support agent (Claude-powered)
├── case-documentation/
│   ├── incidents/                # Incident reports for concerning events
│   ├── appointments/             # Appointment logs
│   ├── treatments/               # Treatment notes
│   └── communications/           # Logs of calls, emails, conversations with staff
├── medical-records/
│   ├── lab-results/              # Blood work, test results
│   ├── prescriptions/            # Medication records
│   └── dialysis-sessions/        # Per-session dialysis logs
├── legal-advocacy/
│   ├── complaint-letters/        # Drafted complaints to facilities/agencies
│   ├── patient-rights/           # Reference documents on patient rights
│   └── evidence/                 # Photos, scanned documents, supporting materials
└── resources/                    # Reference guides and care standards
```

## Quick Start

### Run the AI Support Agent

```bash
cd joseph-support/agent
pip install -r requirements.txt
python health_support_agent.py
```

The agent will help you:
- Document new incidents with guided prompts
- Review and summarize the case
- Understand patient rights
- Draft complaint letters to facilities or oversight bodies
- Prepare questions for medical appointments

### Document an Incident

Copy `case-documentation/incidents/TEMPLATE_incident_report.md` and rename it:
```
YYYY-MM-DD_incident_[short_description].md
```

### Log a Dialysis Session

Copy `medical-records/dialysis-sessions/TEMPLATE_dialysis_session.md` and rename it:
```
YYYY-MM-DD_session.md
```

## Key Resources

- **Patient Rights**: `legal-advocacy/patient-rights/patient_rights_reference.md`
- **Dialysis Care Standards**: `resources/dialysis_care_standards.md`
- **Who to Report To**: `resources/reporting_contacts.md`

## Important Notes

- Date every document consistently: `YYYY-MM-DD`
- Be factual and specific — record times, names (if known), and exact statements
- Keep original copies of all paperwork; scan or photograph everything
- Do not share this folder publicly — it contains private health information
