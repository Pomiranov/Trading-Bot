export type SceneMode =
  | "hero"
  | "frozen-strategies"
  | "trust-architecture"
  | "quant-engine"
  | "final-cta";

export interface SceneModePreset {
  nodeCount: number;
  seed: number;
  /** Sphere scale in world units. */
  radius: number;
  cameraDistance: number;
  fov: number;
  /** rad/s ambient group rotation. */
  rotationSpeed: number;
  /** Hero only: pointer influences camera (max 3deg tilt). */
  interactive: boolean;
}

/**
 * One shared scene, five presets — not five rebuilt scenes. Hero gets the
 * full node count and pointer interactivity; the four "resting state"
 * section instances get a smaller, calmer, non-interactive read of the
 * same network.
 */
export const SCENE_PRESETS: Record<SceneMode, SceneModePreset> = {
  hero: {
    nodeCount: 16,
    seed: 42,
    radius: 3,
    cameraDistance: 8,
    fov: 45,
    rotationSpeed: 0.03,
    interactive: true,
  },
  "frozen-strategies": {
    nodeCount: 8,
    seed: 7,
    radius: 1.6,
    cameraDistance: 5,
    fov: 40,
    rotationSpeed: 0.015,
    interactive: false,
  },
  "trust-architecture": {
    nodeCount: 10,
    seed: 19,
    radius: 1.8,
    cameraDistance: 5,
    fov: 40,
    rotationSpeed: 0.015,
    interactive: false,
  },
  "quant-engine": {
    nodeCount: 12,
    seed: 31,
    radius: 2,
    cameraDistance: 5.5,
    fov: 40,
    rotationSpeed: 0.02,
    interactive: false,
  },
  "final-cta": {
    nodeCount: 8,
    seed: 53,
    radius: 1.6,
    cameraDistance: 5,
    fov: 40,
    rotationSpeed: 0.015,
    interactive: false,
  },
};
