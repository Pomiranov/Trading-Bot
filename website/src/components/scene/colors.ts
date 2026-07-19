/**
 * Three.js materials need real color values, not CSS custom properties.
 * These must stay in sync with src/styles/tokens/color.css by hand — there
 * are only two, so a build-time sync step isn't worth the complexity yet.
 */
export const SCENE_COLORS = {
  bg: "#0a0a0b",
  live: "#e8a33d", // --color-accent
  // rgb(123,123,124) — same value as --color-text-tertiary post-contrast-fix
  frozen: "#7b7b7c",
} as const;
