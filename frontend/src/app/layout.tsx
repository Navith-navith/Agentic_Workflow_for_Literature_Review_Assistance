// app/layout.tsx — Root layout with global styles and fonts

import type { Metadata } from "next";
import { DM_Serif_Display, IBM_Plex_Mono, Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
});

const dmSerif = DM_Serif_Display({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-display",
  display: "swap",
});

const ibmMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MedRAG — Healthcare Research Intelligence",
  description:
    "Agent-based hybrid RAG system for intelligent exploration of healthcare engineering research papers",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${dmSerif.variable} ${ibmMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
