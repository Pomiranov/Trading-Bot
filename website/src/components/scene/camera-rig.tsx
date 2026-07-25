"use client";

import { useRef, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const MAX_TILT = THREE.MathUtils.degToRad(3);

/**
 * Ambient rotation (brief spec: 0.03 rad/s) plus, on interactive
 * instances only, a subtle pointer-driven tilt capped at 3deg. Reads
 * `state.pointer` directly inside useFrame — no useState/re-render in the
 * loop, per the continuous-value rule.
 *
 * Two nested groups so the two rotations don't fight on the same axis:
 * the outer group owns the continuous Y auto-rotation, the inner group
 * owns the pointer tilt (pitch on X, roll on Z), lerped toward target.
 */
export function SceneRig({
  rotationSpeed,
  interactive,
  children,
}: {
  rotationSpeed: number;
  interactive: boolean;
  children: ReactNode;
}) {
  const outerRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Group>(null);

  useFrame((state, delta) => {
    if (outerRef.current) {
      outerRef.current.rotation.y += rotationSpeed * delta;
    }

    if (interactive && innerRef.current) {
      const targetPitch = -state.pointer.y * MAX_TILT;
      const targetRoll = state.pointer.x * MAX_TILT;
      innerRef.current.rotation.x = THREE.MathUtils.lerp(
        innerRef.current.rotation.x,
        targetPitch,
        0.05,
      );
      innerRef.current.rotation.z = THREE.MathUtils.lerp(
        innerRef.current.rotation.z,
        targetRoll,
        0.05,
      );
    }
  });

  return (
    <group ref={outerRef}>
      <group ref={innerRef}>{children}</group>
    </group>
  );
}
