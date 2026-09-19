# Submitting a report

Citizens can submit a report by speaking, typing, or attaching a photo (or a
combination of these) through the citizen portal.

## Supported languages

The citizen portal supports English, Hindi, Bengali, Odia, Urdu, and
Santali. For voice reports, translation and text-to-speech are handled by
the Bhashini pipeline for most languages; Santali has no Bhashini support at
all, so it is instead served by a separate, self-hosted Santali
speech/translation service. Santali's on-screen text is available, but full
voice pipeline coverage for it is more limited than the other five
languages.

## What happens right after you submit

1. If you spoke your report, it is transcribed to text.
2. Personal information is scrubbed from the text before anything else
   touches it.
3. The text is translated into English (if it wasn't already) — this
   English version is what every later stage reasons about, though your
   original language is preserved for showing things back to you.
4. If you attached a photo, it is analysed for relevant visual evidence,
   and its location (from the photo's GPS data, or a location you provide)
   is captured.
5. The report is then classified and handed to the Triage and Route stage,
   which checks for duplicates and assigns it a priority before a human
   operator reviews it.

You'll get a ticket ID once your report has been processed, which you can
use to track its status at any time.
