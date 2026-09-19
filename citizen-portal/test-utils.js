import { render } from "@testing-library/react";
import { LanguageProvider } from "@/context/LanguageProvider";

// Every page reads copy via useLanguage(), which throws outside a
// <LanguageProvider> (see context/LanguageProvider.js) - app/layout.js
// supplies that in the real app, so tests that render a bare page need the
// same wrapper.
export function renderWithProviders(ui) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

// Matches lib/auth.js's TOKEN_PREFIX + verifyStaffCredentials contract -
// simulates an already-signed-in staff member so useStaffGate's redirect-if-
// signed-out effect doesn't fire, without reaching into lib/auth internals.
export function signInAsStaff(portal) {
  window.sessionStorage.setItem(`sahyog_staff_token_${portal}`, "Basic dGVzdA==");
}

export * from "@testing-library/react";
