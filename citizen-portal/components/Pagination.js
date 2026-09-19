"use client";

import { useLanguage } from "@/context/LanguageProvider";

// Plain client-side pager for admin tables whose backend endpoint returns
// the full list with no limit/offset support (unlike /api/tickets, which
// gets real backend-paged "Load more" instead - see operator/queue/page.js).
export default function Pagination({ page, pageCount, onPageChange }) {
  const { t } = useLanguage();
  if (pageCount <= 1) return null;

  return (
    <div className="mt-3 flex items-center justify-between text-sm">
      <button
        type="button"
        className="gov-btn-secondary px-3 py-1 text-xs"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        {t("common.back")}
      </button>
      <span className="text-gray-600">{t("common.pageOf").replace("{page}", page).replace("{count}", pageCount)}</span>
      <button
        type="button"
        className="gov-btn-secondary px-3 py-1 text-xs"
        disabled={page >= pageCount}
        onClick={() => onPageChange(page + 1)}
      >
        {t("common.next")}
      </button>
    </div>
  );
}
