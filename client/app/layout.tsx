import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "SpeechPath", description: "Speech Therapy Platform" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#FFFDF5]">{children}</body>
    </html>
  );
}
