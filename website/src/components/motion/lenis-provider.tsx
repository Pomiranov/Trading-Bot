"use client";

import { useEffect } from "react";
import { initScrollDriver } from "./scroll-driver";

/** Mounted once in the locale root layout. */
export function LenisProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const cleanup = initScrollDriver();
    return cleanup;
  }, []);

  return children;
}
