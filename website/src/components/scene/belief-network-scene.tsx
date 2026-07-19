"use client";

import { useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { PerformanceMonitor } from "@react-three/drei";
import { generateBeliefNetwork } from "@/lib/scene/belief-network-data";
import { SCENE_PRESETS, type SceneMode } from "./scene-config";
import { SceneRig } from "./camera-rig";
import { Nodes } from "./nodes";
import { Edges } from "./edges";

export interface BeliefNetworkSceneProps {
  mode: SceneMode;
  className?: string;
  /** Fired once the Canvas has painted its first frame — Hero uses this
   * to swap out its loading skeleton. */
  onFirstFrame?: () => void;
}

export function BeliefNetworkScene({
  mode,
  className,
  onFirstFrame,
}: BeliefNetworkSceneProps) {
  const preset = SCENE_PRESETS[mode];
  const { nodes, edges } = useMemo(
    () => generateBeliefNetwork(preset.nodeCount, preset.seed),
    [preset.nodeCount, preset.seed],
  );

  // Adaptive quality: PerformanceMonitor fires occasionally (not per
  // frame), so useState here is the right tool, not a continuous-value
  // violation. Downshifts by rendering fewer particles/nodes under load.
  const [degraded, setDegraded] = useState(false);
  const visibleNodes = degraded ? nodes.slice(0, Math.ceil(nodes.length * 0.6)) : nodes;
  const visibleEdges = degraded
    ? edges.filter((e) => e.a < visibleNodes.length && e.b < visibleNodes.length)
    : edges;

  return (
    <Canvas
      className={className}
      dpr={[1, 2]}
      camera={{ position: [0, 0, preset.cameraDistance], fov: preset.fov }}
      gl={{ alpha: true, antialias: true, preserveDrawingBuffer: true }}
      onCreated={() => onFirstFrame?.()}
    >
      <PerformanceMonitor
        onDecline={() => setDegraded(true)}
        onIncline={() => setDegraded(false)}
      />
      <ambientLight intensity={0.4} />
      <pointLight position={[4, 4, 4]} intensity={40} />
      <SceneRig rotationSpeed={preset.rotationSpeed} interactive={preset.interactive}>
        <Nodes nodes={visibleNodes} radius={preset.radius} />
        <Edges nodes={nodes} edges={visibleEdges} radius={preset.radius} />
      </SceneRig>
    </Canvas>
  );
}
