import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = { title: "SpeechPath", description: "Speech Therapy Platform" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neo-bg bg-pattern-grid text-neo-black">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
