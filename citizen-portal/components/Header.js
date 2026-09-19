"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/context/LanguageProvider";
import { LANGUAGES } from "@/lib/languages";

const CITIZEN_NAV = [
  { href: "/", key: "nav.home" },
  { href: "/submit", key: "nav.report" },
  { href: "/track", key: "nav.track" },
  { href: "/transparency", key: "nav.transparency" },
  { href: "/about", key: "nav.about" },
];

const OPERATOR_NAV = [{ href: "/operator/queue", key: "operator.queueTitle" }];

const INSTITUTION_NAV = [
  { href: "/institution", key: "institution.dashboardTitle" },
  { href: "/institution/matches", key: "institution.inboxTitle" },
  { href: "/institution/projects", key: "institution.projectsTitle" },
  { href: "/institution/partners", key: "institution.partnersTitle" },
];

const GOVERNMENT_NAV = [
  { href: "/government", key: "government.overviewTitle" },
  { href: "/government/audit", key: "government.auditTitle" },
];

function portalFor(pathname) {
  if (pathname?.startsWith("/operator")) return "operator";
  if (pathname?.startsWith("/institution")) return "institution";
  if (pathname?.startsWith("/government")) return "government";
  return "citizen";
}

export default function Header() {
  const { t, lang, setLang } = useLanguage();
  const pathname = usePathname();
  const portal = portalFor(pathname);

  const navItems =
    portal === "operator"
      ? OPERATOR_NAV
      : portal === "institution"
        ? INSTITUTION_NAV
        : portal === "government"
          ? GOVERNMENT_NAV
          : CITIZEN_NAV;

  const brandHref = portal === "citizen" ? "/" : `/${portal}`;
  const brandSub =
    portal === "operator"
      ? t("header.operatorBadge")
      : portal === "institution"
        ? t("header.institutionBadge")
        : portal === "government"
          ? t("header.governmentBadge")
          : t("header.brandSub");

  return (
    <header className="border-b-4 border-gov-orange-600 bg-gov-blue-700 text-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link href={brandHref} className="flex items-baseline gap-2">
          <span className="font-serif text-2xl font-bold tracking-tight">{t("header.brand")}</span>
          <span className="hidden text-xs text-gov-blue-100 sm:inline">{brandSub}</span>
        </Link>

        <nav aria-label="Primary" className="flex flex-wrap items-center gap-1 text-sm">
          {navItems.map((item) => {
            // Exact match for a portal's own root link (e.g. "/institution")
            // so it doesn't stay highlighted on every deeper sub-page that
            // happens to share the same prefix (e.g. "/institution/matches").
            const isPortalRoot = item.href === "/" || item.href === `/${portal}`;
            const active = isPortalRoot ? pathname === item.href : pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-md px-3 py-2 font-medium transition-colors ${
                  active ? "bg-gov-blue-900 text-white" : "text-gov-blue-50 hover:bg-gov-blue-800"
                }`}
              >
                {t(item.key)}
              </Link>
            );
          })}

          {portal === "citizen" && (
            <label className="ml-2">
              <span className="sr-only">{t("nav.language")}</span>
              <select
                value={lang}
                onChange={(e) => setLang(e.target.value)}
                className="rounded-md border border-gov-blue-400 bg-gov-blue-700 px-2 py-2 font-medium text-white"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code} className="text-gray-900">
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
          )}
        </nav>
      </div>
    </header>
  );
}
