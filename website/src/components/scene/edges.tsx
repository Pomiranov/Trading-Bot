"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import type { BeliefEdge, BeliefNode } from "@/lib/scene/belief-network-data";
import { SCENE_COLORS } from "./colors";

function scaledPosition(node: BeliefNode, radius: number): [number, number, number] {
  return [
    node.position[0] * radius,
    node.position[1] * radius,
    node.position[2] * radius,
  ];
}

function EdgeLine({
  from,
  to,
  strength,
  live,
}: {
  from: [number, number, number];
  to: [number, number, number];
  strength: number;
  live: boolean;
}) {
  return (
    <Line
      points={[from, to]}
      color={live ? SCENE_COLORS.live : SCENE_COLORS.frozen}
      transparent
      opacity={live ? 0.35 : 0.12}
      lineWidth={0.5 + strength * 1.5}
    />
  );
}

/** A single glinting point drifting along its edge — "live decision
 * signals" per the brief. Only rendered on edges touching a live node;
 * dormant edges stay static hairlines. */
function FlowParticle({
  from,
  to,
  speed,
}: {
  from: [number, number, number];
  to: [number, number, number];
  speed: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const offset = useRef(Math.random());

  useFrame((state) => {
    if (!ref.current) return;
    const t = (state.clock.elapsedTime * speed + offset.current) % 1;
    ref.current.position.set(
      THREE.MathUtils.lerp(from[0], to[0], t),
      THREE.MathUtils.lerp(from[1], to[1], t),
      THREE.MathUtils.lerp(from[2], to[2], t),
    );
    const fade = Math.sin(t * Math.PI); // fade in/out at each end
    (ref.current.material as THREE.MeshBasicMaterial).opacity = fade;
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.035, 8, 8]} />
      <meshBasicMaterial color={SCENE_COLORS.live} transparent opacity={0} />
    </mesh>
  );
}

export function Edges({
  nodes,
  edges,
  radius,
}: {
  nodes: BeliefNode[];
  edges: BeliefEdge[];
  radius: number;
}) {
  return (
    <>
      {edges.map((edge, i) => {
        const nodeA = nodes[edge.a];
        const nodeB = nodes[edge.b];
        const from = scaledPosition(nodeA, radius);
        const to = scaledPosition(nodeB, radius);
        const live = nodeA.live || nodeB.live;

        return (
          <group key={`${edge.a}-${edge.b}-${i}`}>
            <EdgeLine from={from} to={to} strength={edge.strength} live={live} />
            {live ? (
              <FlowParticle from={from} to={to} speed={0.15 + edge.strength * 0.25} />
            ) : null}
          </group>
        );
      })}
    </>
  );
}
