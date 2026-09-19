"use client";

import { useRouter } from "next/navigation";
import BasicAuthScreen from "@/components/BasicAuthScreen";

export default function InstitutionLoginPage() {
  const router = useRouter();
  return <BasicAuthScreen portal="institution" onSignedIn={() => router.push("/institution")} />;
}
