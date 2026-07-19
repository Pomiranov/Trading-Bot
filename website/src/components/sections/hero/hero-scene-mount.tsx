"use client";

import { useState } from "react";
import Image from "next/image";
import { BeliefNetworkSceneLazy } from "@/components/scene/belief-network-scene.lazy";
import { useSceneCapability } from "@/components/scene/use-scene-capability";

/**
 * Hero is the one eager instance (above the fold) — still dynamically
 * imported, but not intersection-gated like the later section instances.
 * The capability check happens BEFORE the dynamic import is even
 * requested: on the reduced-motion/low-end/no-WebGL2 path, Three.js/R3F
 * are never fetched at all, not just hidden.
 */
export function HeroSceneMount({ caption }: { caption: string }) {
  const { ready, canRender3D } = useSceneCapability();
  const [firstFrame, setFirstFrame] = useState(false);

  return (
    <div
      className="relative aspect-square w-full max-w-[560px] shrink-0"
      aria-hidden="true"
    >
      {!ready ? (
        // Same markup on server + first client paint — no hydration
        // mismatch — swapped once the capability check resolves.
        <div className="absolute inset-0 rounded-[var(--radius-lg)] bg-[color:var(--color-surface)]" />
      ) : canRender3D ? (
        <>
          {!firstFrame ? (
            <div className="absolute inset-0 animate-pulse rounded-[var(--radius-lg)] bg-[color:var(--color-surface)]" />
          ) : null}
          <BeliefNetworkSceneLazy
            mode="hero"
            className="absolute inset-0"
            onFirstFrame={() => setFirstFrame(true)}
          />
        </>
      ) : (
        <Image
          src="/fallback/hero.png"
          alt=""
          fill
          priority
          sizes="(min-width: 768px) 560px, 100vw"
          className="rounded-[var(--radius-lg)] object-contain"
        />
      )}
      <span className="sr-only">{caption}</span>
    </div>
  );
}
