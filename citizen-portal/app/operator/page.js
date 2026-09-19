import { redirect } from "next/navigation";

// The operator portal has one real screen (the queue) - this only exists so
// Header.js's brandHref ("/operator") has somewhere to land instead of 404ing,
// same fix as the new /institution dashboard for the institution portal.
export default function OperatorRootPage() {
  redirect("/operator/queue");
}
