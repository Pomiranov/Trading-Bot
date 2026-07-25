"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { BeliefNetworkSceneLazy } from "./belief-network-scene.lazy";
import { useSceneCapability } from "./use-scene-capability";
import { useInView } from "./use-in-view";
import type { SceneMode } from "./scene-config";
import { track } from "@/lib/analytics/events";

/**
 * The four "resting state" section instances (frozen-strategies,
 * trust-architecture, quant-engine, final-cta) — intersection-gated
 * (unlike Hero, which is eager): the dynamic import is never even
 * requested until the section is about to scroll into view.
 *
 * Fallback poster: reusing public/fallback/hero.png for now (a real
 * capture of the actual scene, just not mode-specific — this session's
 * screenshot tooling couldn't reliably capture the other 4 modes; swap in
 * per-mode captures as a follow-up once that's unblocked).
 */
export function SectionSceneMount({
  mode,
  caption,
  className,
}: {
  mode: SceneMode;
  caption: string;
  className?: string;
}) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const { ready, canRender3D } = useSceneCapability();
  const [firstFrame, setFirstFrame] = useState(false);
  const [engaged, setEngaged] = useState(false);

  useEffect(() => {
    if (inView && ready && !canRender3D) {
      track({ name: "scene_interaction", props: { mode, state: "fallback_shown" } });
    }
  }, [inView, ready, canRender3D, mode]);

  return (
    <div
      ref={ref}
      className={`relative aspect-square w-full ${className ?? ""}`}
      aria-hidden="true"
      onPointerEnter={() => {
        if (engaged) return;
        setEngaged(true);
        track({ name: "scene_interaction", props: { mode, state: "pointer_engaged" } });
      }}
    >
      {!inView || !ready ? (
        <div className="absolute inset-0 rounded-[var(--radius-lg)] bg-[color:var(--color-surface)]" />
      ) : canRender3D ? (
        <>
          {!firstFrame ? (
            <div className="absolute inset-0 animate-pulse rounded-[var(--radius-lg)] bg-[color:var(--color-surface)]" />
          ) : null}
          <BeliefNetworkSceneLazy
            mode={mode}
            className="absolute inset-0"
            onFirstFrame={() => {
              setFirstFrame(true);
              track({ name: "scene_interaction", props: { mode, state: "mounted" } });
            }}
          />
        </>
      ) : (
        <Image
          src="/fallback/hero.png"
          alt=""
          fill
          sizes="(min-width: 768px) 400px, 100vw"
          className="rounded-[var(--radius-lg)] object-contain"
        />
      )}
      <span className="sr-only">{caption}</span>
    </div>
  );
}
