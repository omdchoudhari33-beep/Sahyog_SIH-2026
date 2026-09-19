// Languages offered on the citizen portal's language dropdown. Santali
// (Ol Chiki script) is UI-only - see the header comment in lib/dict.js:
// Bhashini, the real speech/translation backend, has no ASR or translation
// model for it at all (confirmed against this project's own API key), so
// selecting it changes the interface language but voice input and
// AI translation are not available in it yet.
export const LANGUAGES = [
  { code: "en", label: "English", rtl: false },
  { code: "hi", label: "हिन्दी", rtl: false },
  { code: "bn", label: "বাংলা", rtl: false },
  { code: "or", label: "ଓଡ଼ିଆ", rtl: false },
  { code: "ur", label: "اردو", rtl: true },
  { code: "sat", label: "ᱥᱟᱱᱛᱟᱲᱤ", rtl: false },
];

export const LANGUAGE_CODES = LANGUAGES.map((l) => l.code);

export function isRtl(code) {
  return LANGUAGES.find((l) => l.code === code)?.rtl ?? false;
}
