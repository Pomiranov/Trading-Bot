import { Geist, Geist_Mono } from "next/font/google";

// Self-hosted at build time by next/font — no runtime request to Google Fonts,
// no FOUT (font-display handled automatically with fallback metrics).

export const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin", "cyrillic"],
  display: "swap",
});

export const geistMono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin", "cyrillic"],
  display: "swap",
});

export const fontVariables = `${geistSans.variable} ${geistMono.variable}`;
