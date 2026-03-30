Silently scan Joseph's health support case and produce a concise status update.

Steps:
1. Use Glob to list all files in `joseph-support/case-documentation/incidents/` (exclude TEMPLATE files).
2. Use Glob to list all files in `joseph-support/case-documentation/communications/` (exclude TEMPLATE files).
3. Read every incident file found.
4. Read every communication file found.

Then output a short, structured summary in this format:

---

**Joseph Health Case — Status Update**
*As of [today's date]*

**Incidents Documented:** [count]
**Communications Logged:** [count]

**Recent Activity:**
[List the 3 most recent incidents or communications by date, one line each]

**Patterns / Red Flags:**
[Any recurring issues — e.g., "3 reports of shortened sessions", "2 incidents of staff dismissing complaints"]

**Outstanding Actions:**
[Any incidents marked as "documented only" with no follow-up filed]

**Recommended Next Step:**
[One clear suggestion — e.g., "Consider filing a formal complaint with the ESRD Network given the pattern of shortened sessions documented on [dates]."]

---

Be factual, brief, and actionable. If no incidents are documented yet, say so and encourage the family to begin logging using `/joseph`.
