import { Noto_Sans, Noto_Serif } from "next/font/google";
import "./globals.css";
import { LanguageProvider } from "@/context/LanguageProvider";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const notoSerif = Noto_Serif({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-noto-serif",
  display: "swap",
});

const notoSans = Noto_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-noto-sans",
  display: "swap",
});

export const metadata = {
  title: "Sahyog - Jharkhand Grievance Redressal Portal",
  description:
    "Report civic problems in your own language and track how the Government of Jharkhand responds - a Smart India Hackathon 2026 demonstration build.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${notoSerif.variable} ${notoSans.variable}`}>
      <body>
        <LanguageProvider>
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:shadow"
          >
            Skip to main content
          </a>
          <Header />
          <main id="main-content" className="flex-1">
            {children}
          </main>
          <Footer />
        </LanguageProvider>
      </body>
    </html>
  );
}
