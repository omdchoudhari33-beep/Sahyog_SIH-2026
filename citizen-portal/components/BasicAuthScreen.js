"use client";

import { useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { verifyStaffCredentials } from "@/lib/auth";

// Shared login screen for the two staff portals. The password is checked
// against the Orchestrator's real HTTPBasic admin gate (lib/auth.js) - both
// portals share one staff credential; the username field isn't checked by
// the backend, but is kept for a familiar login form.
export default function BasicAuthScreen({ portal, onSignedIn }) {
  const { t } = useLanguage();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError(t("common.errorGeneric"));
      return;
    }
    setBusy(true);
    setError(null);
    const result = await verifyStaffCredentials(portal, password);
    setBusy(false);
    if (!result.ok) {
      setError(result.error === "invalid_credentials" ? t(`${portal}.loginInvalid`) : t("common.errorGeneric"));
      return;
    }
    onSignedIn();
  }

  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="font-serif text-2xl font-semibold text-gov-blue-900">{t(`${portal}.loginHeading`)}</h1>
      <p className="mt-1 text-sm text-gray-600">{t(`${portal}.loginSub`)}</p>

      <form onSubmit={handleSubmit} className="gov-card mt-6 space-y-4 p-5">
        <div>
          <label htmlFor="staff-username" className="gov-label">
            {t(`${portal}.usernameLabel`)}
          </label>
          <input
            id="staff-username"
            type="text"
            autoComplete="username"
            className="gov-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="staff-password" className="gov-label">
            {t(`${portal}.passwordLabel`)}
          </label>
          <input
            id="staff-password"
            type="password"
            autoComplete="current-password"
            className="gov-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}

        <button type="submit" className="gov-btn-primary w-full" disabled={busy}>
          {busy ? t("common.loading") : t(`${portal}.loginButton`)}
        </button>
      </form>

      <p className="mt-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        {t(`${portal}.loginNote`)}
      </p>
    </div>
  );
}
