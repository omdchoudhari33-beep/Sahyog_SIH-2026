// Generic status pill for the staff portals' own domain vocabularies (HEI
// match status, pilot disposition, funding ledger status, ...) - distinct
// from StatusBadge, which is hardwired to the citizen-facing STATUS_KEYS
// vocabulary (see lib/status.js) and looks up its label via `status.*`.
// Tailwind class names must appear as full literal strings somewhere in the
// source for the JIT compiler to pick them up, so this stays a lookup
// object rather than string-building the classes from `tone`.
const TONE_CLASSES = {
  neutral: "bg-gray-100 text-gray-700 border-gray-300",
  pending: "bg-amber-50 text-amber-800 border-amber-300",
  success: "bg-green-50 text-green-800 border-green-300",
  info: "bg-gov-blue-50 text-gov-blue-800 border-gov-blue-200",
  danger: "bg-red-50 text-red-800 border-red-300",
};

export default function AdminBadge({ label, tone = "neutral" }) {
  const classes = TONE_CLASSES[tone] || TONE_CLASSES.neutral;
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${classes}`}>
      {label}
    </span>
  );
}
