import { Geist, Geist_Mono, Cormorant_Garamond } from "next/font/google";

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

// Serif accent — used only for the hero tagline and philosophy pull-quotes.
// Free rotation choice (taste-skill approved pool); swap for a licensed
// Canela / GT Sectra later by changing only this declaration.
export const cormorantGaramond = Cormorant_Garamond({
  variable: "--font-serif",
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

export const fontVariables = `${geistSans.variable} ${geistMono.variable} ${cormorantGaramond.variable}`;
