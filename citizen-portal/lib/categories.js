// The full, real CivicDomain enum classified by Agent 2's C1 text model
// (see "2.Evidence Extractor/schemas.py" - verified against source, not
// guessed). Since the citizen submit flow has no category picker any more
// (domain is entirely AI-detected), a report can land on ANY of these, not
// just the handful a picker would have offered - so every domain the real
// classifier can produce needs a real label here, in every language a
// citizen might be reading in, or ProblemCard/TicketRow/dashboards would
// show a raw enum string like "ILLEGAL_CONSTRUCTION_ENCROACHMENT" verbatim.
export const DOMAINS = [
  {
    id: "ENERGY_POWER",
    en: "Electricity",
    hi: "बिजली",
    bn: "বিদ্যুৎ",
    or: "ବିଦ୍ୟୁତ",
    ur: "بجلی",
  },
  {
    id: "ROADS_BRIDGES",
    en: "Roads & Bridges",
    hi: "सड़क और पुल",
    bn: "সড়ক ও সেতু",
    or: "ସଡ଼କ ଓ ସେତୁ",
    ur: "سڑکیں اور پل",
  },
  {
    id: "WATER_SUPPLY",
    en: "Water Supply",
    hi: "जलापूर्ति",
    bn: "জল সরবরাহ",
    or: "ଜଳ ଯୋଗାଣ",
    ur: "پانی کی فراہمی",
  },
  {
    id: "SANITATION_SEWAGE",
    en: "Sanitation & Sewage",
    hi: "स्वच्छता और सीवरेज",
    bn: "স্যানিটেশন ও নিকাশি",
    or: "ପରିମଳ ଏବଂ ନାଳ",
    ur: "صفائی اور نکاسی",
  },
  {
    id: "WASTE_GARBAGE_COLLECTION",
    en: "Garbage Collection",
    hi: "कचरा संग्रहण",
    bn: "বর্জ্য সংগ্রহ",
    or: "ଅଳିଆ ସଂଗ୍ରହ",
    ur: "کچرا اٹھانا",
  },
  {
    id: "STREETLIGHTING",
    en: "Streetlighting",
    hi: "स्ट्रीट लाइट",
    bn: "স্ট্রিট লাইট",
    or: "ସ୍ଟ୍ରିଟ୍ ଲାଇଟ୍",
    ur: "اسٹریٹ لائٹ",
  },
  {
    id: "DRAINAGE_WATERLOGGING",
    en: "Drainage / Waterlogging",
    hi: "जलनिकासी / जलभराव",
    bn: "নিকাশি / জলাবদ্ধতা",
    or: "ଜଳ ନିଷ୍କାସନ / ଜଳଭରା",
    ur: "نکاسی / پانی جمع ہونا",
  },
  {
    id: "ILLEGAL_CONSTRUCTION_ENCROACHMENT",
    en: "Illegal Construction / Encroachment",
    hi: "अवैध निर्माण / अतिक्रमण",
    bn: "অবৈধ নির্মাণ / দখল",
    or: "ଅବୈଧ ନିର୍ମାଣ / ଅନଧିକାର ପ୍ରବେଶ",
    ur: "غیر قانونی تعمیر / قبضہ",
  },
  {
    id: "STRAY_ANIMAL_MANAGEMENT",
    en: "Stray Animal Management",
    hi: "आवारा पशु प्रबंधन",
    bn: "বেওয়ারিশ পশু ব্যবস্থাপনা",
    or: "ମାଡ଼ିଆ ପଶୁ ପରିଚାଳନା",
    ur: "آوارہ جانوروں کا انتظام",
  },
  {
    id: "PARKS_PUBLIC_SPACES",
    en: "Parks & Public Spaces",
    hi: "पार्क और सार्वजनिक स्थान",
    bn: "পার্ক ও সরকারি স্থান",
    or: "ପାର୍କ ଏବଂ ସାର୍ବଜନୀନ ସ୍ଥାନ",
    ur: "پارکس اور عوامی مقامات",
  },
  {
    id: "HEALTHCARE_FACILITY_MAINTENANCE",
    en: "Healthcare Facility Maintenance",
    hi: "स्वास्थ्य सुविधा रखरखाव",
    bn: "স্বাস্থ্য সুবিধা রক্ষণাবেক্ষণ",
    or: "ସ୍ୱାସ୍ଥ୍ୟ ସୁବିଧା ରକ୍ଷଣାବେକ୍ଷଣ",
    ur: "صحت کی سہولت کی مرمت",
  },
  {
    id: "EDUCATION_FACILITY_MAINTENANCE",
    en: "Education Facility Maintenance",
    hi: "शिक्षा सुविधा रखरखाव",
    bn: "শিক্ষা সুবিধা রক্ষণাবেক্ষণ",
    or: "ଶିକ୍ଷା ସୁବିଧା ରକ୍ଷଣାବେକ୍ଷଣ",
    ur: "تعلیمی سہولت کی مرمت",
  },
  {
    id: "TRAFFIC_SIGNAGE",
    en: "Traffic & Signage",
    hi: "यातायात और संकेत",
    bn: "ট্রাফিক ও সাইনেজ",
    or: "ଟ୍ରାଫିକ୍ ଏବଂ ସାଇନେଜ୍",
    ur: "ٹریفک اور سائن بورڈ",
  },
  {
    id: "CIVIC_DISASTER_EMERGENCY",
    en: "Civic Disaster / Emergency",
    hi: "नागरिक आपदा / आपात स्थिति",
    bn: "নাগরিক দুর্যোগ / জরুরি অবস্থা",
    or: "ନାଗରିକ ବିପତ୍ତି / ଜରୁରୀକାଳୀନ",
    ur: "شہری آفت / ہنگامی حالت",
  },
  // Broader societal-challenge domains, added alongside the municipal-
  // infrastructure ones above (not replacing them) - see
  // "2.Evidence Extractor/schemas.py"'s CivicDomain enum. Hindi/Bengali/
  // Odia/Urdu here are best-effort, not verified by a native speaker -
  // review before relying on them in production.
  {
    id: "HEALTHCARE_SERVICE_GAP",
    en: "Healthcare Access / Quality",
    hi: "स्वास्थ्य सेवा उपलब्धता",
    bn: "স্বাস্থ্যসেবা প্রাপ্যতা",
    or: "ସ୍ୱାସ୍ଥ୍ୟ ସେବା ଉପଲବ୍ଧତା",
    ur: "صحت کی خدمات کی دستیابی",
  },
  {
    id: "EDUCATION_ACCESS_QUALITY",
    en: "Education Access / Quality",
    hi: "शिक्षा की उपलब्धता एवं गुणवत्ता",
    bn: "শিক্ষার সুযোগ ও গুণমান",
    or: "ଶିକ୍ଷାର ଉପଲବ୍ଧତା ଏବଂ ଗୁଣାତ୍ମକତା",
    ur: "تعلیم کی دستیابی اور معیار",
  },
  {
    id: "AGRICULTURE_LIVELIHOOD",
    en: "Agriculture & Farmer Livelihood",
    hi: "कृषि एवं किसान आजीविका",
    bn: "কৃষি ও কৃষক জীবিকা",
    or: "କୃଷି ଏବଂ କୃଷକ ଜୀବିକା",
    ur: "زراعت اور کسان کی روزی",
  },
  {
    id: "WATER_RESOURCE_MANAGEMENT",
    en: "Water Resource Management",
    hi: "जल संसाधन प्रबंधन",
    bn: "জল সম্পদ ব্যবস্থাপনা",
    or: "ଜଳ ସମ୍ପଦ ପରିଚାଳନା",
    ur: "آبی وسائل کا انتظام",
  },
  {
    id: "ACCESSIBILITY_DISABILITY",
    en: "Accessibility for Persons with Disabilities",
    hi: "दिव्यांगजन हेतु सुगम्यता",
    bn: "প্রতিবন্ধীদের জন্য প্রবেশগম্যতা",
    or: "ଦିବ୍ୟାଙ୍ଗଙ୍କ ପାଇଁ ପ୍ରବେଶଯୋଗ୍ୟତା",
    ur: "معذور افراد کے لیے رسائی",
  },
  {
    id: "RURAL_LIVELIHOODS",
    en: "Rural Livelihoods & Employment Schemes",
    hi: "ग्रामीण आजीविका एवं रोजगार योजना",
    bn: "গ্রামীণ জীবিকা ও কর্মসংস্থান প্রকল্প",
    or: "ଗ୍ରାମୀଣ ଜୀବିକା ଏବଂ ନିଯୁକ୍ତି ଯୋଜନା",
    ur: "دیہی روزی اور روزگار اسکیم",
  },
  {
    id: "ENVIRONMENT_POLLUTION",
    en: "Environment & Pollution",
    hi: "पर्यावरण एवं प्रदूषण",
    bn: "পরিবেশ ও দূষণ",
    or: "ପରିବେଶ ଏବଂ ପ୍ରଦୂଷଣ",
    ur: "ماحولیات اور آلودگی",
  },
  {
    id: "PUBLIC_SERVICE_DELIVERY",
    en: "Public Service Delivery",
    hi: "सार्वजनिक सेवा वितरण",
    bn: "সরকারি সেবা প্রদান",
    or: "ସାର୍ବଜନୀନ ସେବା ପ୍ରଦାନ",
    ur: "عوامی خدمات کی فراہمی",
  },
  // Track B (R&D/university-routed) domains - see
  // "2.Evidence Extractor/schemas.py"'s CivicDomain enum comment: these two
  // were added to the backend classifier after the domains above and were
  // missing here entirely, so a report the AI correctly classified into
  // either of them still showed the raw enum string ("UNKNOWN_STRUCTURAL_
  // FAILURE") verbatim in the operator/institution/citizen UI instead of a
  // real label.
  {
    id: "AGRICULTURAL_DISEASE",
    en: "Agricultural Disease / Pest Outbreak",
    hi: "कृषि रोग / कीट प्रकोप",
    bn: "কৃষি রোগ / পোকা প্রাদুর্ভাব",
    or: "କୃଷି ରୋଗ / କୀଟ ପ୍ରକୋପ",
    ur: "زرعی بیماری / کیڑوں کا حملہ",
  },
  {
    id: "UNKNOWN_STRUCTURAL_FAILURE",
    en: "Unexplained Structural Failure",
    hi: "अज्ञात संरचनात्मक विफलता",
    bn: "অজানা কাঠামোগত ব্যর্থতা",
    or: "ଅଜ୍ଞାତ ସାଂରଚନାତ୍ମକ ବିଫଳତା",
    ur: "نامعلوم ساختی ناکامی",
  },
  {
    id: "OTHER_MUNICIPAL",
    en: "Other",
    hi: "अन्य",
    bn: "অন্যান্য",
    or: "ଅନ୍ୟାନ୍ୟ",
    ur: "دیگر",
  },
];

// A couple of legacy/alias spellings seen in older backend code paths
// (validation.py's TRACK_A_DOMAINS fallback set) - map them to the same
// label as their canonical id rather than showing a raw string.
const ALIASES = { ROADS: "ROADS_BRIDGES", WASTE: "WASTE_GARBAGE_COLLECTION" };

export function domainLabel(domain, lang) {
  const id = ALIASES[domain] || domain;
  const d = DOMAINS.find((x) => x.id === id);
  if (!d) return domain || "";
  return d[lang] || d.en;
}
