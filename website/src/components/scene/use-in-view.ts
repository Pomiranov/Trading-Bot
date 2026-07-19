"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Gates when a section's 3D instance mounts — only Hero is eager (see
 * hero-scene-mount.tsx); the four "resting state" instances (added in
 * later phases) use this to defer their JS chunk until the section is
 * about to enter viewport.
 */
export function useInView<T extends HTMLElement>(options?: {
  rootMargin?: string;
  threshold?: number;
}) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || inView) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      {
        rootMargin: options?.rootMargin ?? "200px",
        threshold: options?.threshold ?? 0.25,
      },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [inView, options?.rootMargin, options?.threshold]);

  return { ref, inView };
}
