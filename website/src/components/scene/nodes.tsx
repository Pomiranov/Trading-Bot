"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { BeliefNode } from "@/lib/scene/belief-network-data";
import { SCENE_COLORS } from "./colors";

function Node({ node, radius }: { node: BeliefNode; radius: number }) {
  const meshRef = useRef<THREE.Mesh>(null);

  // Size = confidence (brief spec). Pulse speed is INVERSE to confidence —
  // a calmer, slower pulse reads as "more sophisticated / more certain"
  // than a fast nervous one, which is the deliberate inversion the brief
  // calls for over the naive "high confidence = urgent/fast" instinct.
  const baseScale = 0.08 + node.confidence * 0.14;
  const pulseSpeed = 3 - node.confidence * 2.4;
  const pulseAmplitude = 0.18 - node.confidence * 0.1;
  const phase = node.id * 1.7; // desync nodes so they don't pulse in lockstep

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime;
    const pulse = 1 + Math.sin(t * pulseSpeed + phase) * pulseAmplitude;
    meshRef.current.scale.setScalar(baseScale * pulse);
  });

  const color = node.live ? SCENE_COLORS.live : SCENE_COLORS.frozen;

  return (
    <mesh
      ref={meshRef}
      position={[
        node.position[0] * radius,
        node.position[1] * radius,
        node.position[2] * radius,
      ]}
    >
      <sphereGeometry args={[1, 16, 16]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={node.live ? 0.9 : 0.15}
        roughness={0.4}
        metalness={0.1}
      />
    </mesh>
  );
}

export function Nodes({ nodes, radius }: { nodes: BeliefNode[]; radius: number }) {
  return (
    <>
      {nodes.map((node) => (
        <Node key={node.id} node={node} radius={radius} />
      ))}
    </>
  );
}
