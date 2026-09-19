"use client";

import { useLanguage } from "@/context/LanguageProvider";

export default function AboutPage() {
  const { t } = useLanguage();

  const steps = [
    { title: t("about.step1Title"), body: t("about.step1Body") },
    { title: t("about.step2Title"), body: t("about.step2Body") },
    { title: t("about.step3Title"), body: t("about.step3Body") },
    { title: t("about.step4Title"), body: t("about.step4Body") },
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("about.heading")}</h1>
      <p className="mt-3 text-gray-700">{t("about.intro")}</p>

      <section className="mt-10">
        <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("about.howHeading")}</h2>
        <p className="mt-2 text-gray-700">{t("about.howIntro")}</p>

        <ol className="mt-5 space-y-5">
          {steps.map((step) => (
            <li key={step.title} className="gov-card p-4">
              <h3 className="font-serif text-lg font-semibold text-gov-blue-800">{step.title}</h3>
              <p className="mt-1 text-sm text-gray-700">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-10">
        <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("about.contactHeading")}</h2>
        <p className="mt-2 text-gray-700">{t("about.contactBody")}</p>
      </section>
    </div>
  );
}
