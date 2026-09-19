"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isStaffSignedIn } from "@/lib/auth";

// Shared client-side gate for the operator/institution portals - redirects
// to that portal's login screen if no verified staff token is stored (see
// lib/auth.js's verifyStaffCredentials). Returns true once the check has
// run and passed, so callers can render nothing until then instead of
// flashing gated content.
export function useStaffGate(portal) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isStaffSignedIn(portal)) {
      router.replace(`/${portal}/login`);
      return;
    }
    setReady(true);
  }, [portal, router]);

  return ready;
}
