# What SAHYOG is

SAHYOG is a civic-issue reporting and resolution pipeline. A citizen reports
a problem (a broken streetlight, a pothole, a water leak, and so on) by
voice, text, or photo, and the system carries it through several stages
before it reaches the right government body or partner organisation.

## The pipeline, stage by stage

1. **Language Normalizer** — takes the citizen's raw voice or text report,
   removes personal information (PII scrubbing), transcribes audio to text
   if needed, and translates it into English.
2. **Evidence Extractor** — reads the normalized text (and any photo) with a
   local AI model to classify the civic domain (e.g. roads, water,
   sanitation), estimate severity, pull out mentioned locations, and suggest
   whether the issue looks routine or unusual.
3. **Triage and Route** — checks whether this report is a duplicate of an
   already-active report nearby (both by location and by meaning), merges
   duplicates into one ticket, scores every active ticket by priority, and
   puts each new or updated ticket in front of a human operator (the "DNO")
   who makes the final call.
4. **ULB Dispatch (Track A)** — for routine municipal issues, once an
   operator confirms Track A, this stage routes the ticket to the correct
   Urban Local Body (ULB) department, dispatches it, tracks the response
   time, and verifies the closure proof once the ULB reports it fixed.
5. **Track B Innovation** — for issues that need research or a novel
   solution rather than a routine repair, this stage matches the ticket to
   a higher-education institution (HEI) with relevant capability, forms a
   student/faculty team, and takes a project proposal through nodal officer
   approval.
6. **Industry Partnership** and **Lifecycle Outcome** — once a Track B
   proposal is approved, these stages can bring in an industry partner and
   track the project's milestones, pilot validation, and eventual handover
   back to a ULB or spin-out as a startup.
7. **Transparency Layer** — publishes a public status view of every ticket
   so citizens (and anyone else) can see where a report currently stands.

A human always makes the Track A / Track B decision — the AI only suggests
one, it never decides on its own.
