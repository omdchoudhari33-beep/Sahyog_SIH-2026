"use client";

import { useRouter } from "next/navigation";
import BasicAuthScreen from "@/components/BasicAuthScreen";

export default function OperatorLoginPage() {
  const router = useRouter();
  return <BasicAuthScreen portal="operator" onSignedIn={() => router.push("/operator/queue")} />;
}
