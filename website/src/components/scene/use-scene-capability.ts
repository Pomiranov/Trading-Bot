"use client";

import { useEffect, useState } from "react";

type NavigatorWithHeuristics = Navigator & {
  deviceMemory?: number;
  connection?: { saveData?: boolean };
};

function hasWebGL2(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!canvas.getContext("webgl2");
  } catch {
    return false;
  }
}

/**
 * One-shot environment capability check (not a continuously-updating
 * value — useState is the right tool here, unlike scroll/pointer
 * tracking elsewhere in the scene code). Gates whether the real R3F
 * Canvas mounts at all, or a static poster image renders instead. When
 * the fallback path fires, Three.js/R3F are never even fetched — the
 * gate happens before the dynamic import, not just visually.
 */
export function useSceneCapability(): { ready: boolean; canRender3D: boolean } {
  const [state, setState] = useState({ ready: false, canRender3D: false });

  useEffect(() => {
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const nav = navigator as NavigatorWithHeuristics;
    const lowEndDevice =
      (nav.hardwareConcurrency !== undefined && nav.hardwareConcurrency < 4) ||
      (nav.deviceMemory !== undefined && nav.deviceMemory < 4);
    const saveData = nav.connection?.saveData ?? false;

    const canRender3D =
      !reducedMotion && !lowEndDevice && !saveData && hasWebGL2();

    setState({ ready: true, canRender3D });
  }, []);

  return state;
}
