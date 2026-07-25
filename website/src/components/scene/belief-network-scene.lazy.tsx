"use client";

import dynamic from "next/dynamic";

/**
 * Three.js/R3F never touch the server bundle or the initial client chunk —
 * this is the one place the real scene module is imported.
 */
export const BeliefNetworkSceneLazy = dynamic(
  () => import("./belief-network-scene").then((m) => m.BeliefNetworkScene),
  { ssr: false },
);
