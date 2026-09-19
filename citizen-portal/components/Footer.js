"use client";

import { useLanguage } from "@/context/LanguageProvider";

export default function Footer() {
  const { t } = useLanguage();

  return (
    <footer className="border-t border-gov-blue-100 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-gray-600">
        <div className="flex flex-wrap gap-x-8 gap-y-2 font-medium text-gov-blue-800">
          <span>{t("footer.about")}</span>
          <span>
            {t("footer.helpline")}: {t("footer.helplineNumber")}
          </span>
          <span>{t("footer.privacy")}</span>
          <span>{t("footer.terms")}</span>
        </div>
        <p className="mt-4 max-w-3xl text-gray-500">{t("footer.disclaimer")}</p>
        <p className="mt-2 text-gray-400">{t("footer.copyright")}</p>
      </div>
    </footer>
  );
}
