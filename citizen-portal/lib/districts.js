// Jharkhand's 24 districts. Kept as its own small data file (bilingual
// labels inline) rather than jammed into dict.js, since this is structured
// list data reused by a dropdown and a filter, not prose UI copy.
export const DISTRICTS = [
  { id: "bokaro", en: "Bokaro", hi: "बोकारो" },
  { id: "chatra", en: "Chatra", hi: "चतरा" },
  { id: "deoghar", en: "Deoghar", hi: "देवघर" },
  { id: "dhanbad", en: "Dhanbad", hi: "धनबाद" },
  { id: "dumka", en: "Dumka", hi: "दुमका" },
  { id: "east-singhbhum", en: "East Singhbhum (Jamshedpur)", hi: "पूर्वी सिंहभूम (जमशेदपुर)" },
  { id: "garhwa", en: "Garhwa", hi: "गढ़वा" },
  { id: "giridih", en: "Giridih", hi: "गिरिडीह" },
  { id: "godda", en: "Godda", hi: "गोड्डा" },
  { id: "gumla", en: "Gumla", hi: "गुमला" },
  { id: "hazaribagh", en: "Hazaribagh", hi: "हजारीबाग" },
  { id: "jamtara", en: "Jamtara", hi: "जामताड़ा" },
  { id: "khunti", en: "Khunti", hi: "खूंटी" },
  { id: "koderma", en: "Koderma", hi: "कोडरमा" },
  { id: "latehar", en: "Latehar", hi: "लातेहार" },
  { id: "lohardaga", en: "Lohardaga", hi: "लोहरदगा" },
  { id: "pakur", en: "Pakur", hi: "पाकुड़" },
  { id: "palamu", en: "Palamu", hi: "पलामू" },
  { id: "ramgarh", en: "Ramgarh", hi: "रामगढ़" },
  { id: "ranchi", en: "Ranchi", hi: "रांची" },
  { id: "sahebganj", en: "Sahebganj", hi: "साहिबगंज" },
  { id: "seraikela-kharsawan", en: "Seraikela Kharsawan", hi: "सरायकेला खरसावां" },
  { id: "simdega", en: "Simdega", hi: "सिमडेगा" },
  { id: "west-singhbhum", en: "West Singhbhum (Chaibasa)", hi: "पश्चिमी सिंहभूम (चाईबासा)" },
];

export function districtLabel(id, lang) {
  const d = DISTRICTS.find((x) => x.id === id);
  if (!d) return id || "";
  return lang === "hi" ? d.hi : d.en;
}
