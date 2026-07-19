/**
 * Illustrative belief-network geometry for the 3D hero. This is NOT the
 * real strategy inventory (that's StrategyRecord / the Strategy Layer
 * table, content-layer-backed, three real strategies). The hero visual is
 * a living diagram of the MECHANISM, not a 1:1 chart of production data —
 * more nodes than three real strategies reads as an actual network rather
 * than three dots. Deterministic (seeded PRNG), so layout is stable across
 * renders and reduced-motion static captures.
 */

export interface BeliefNode {
  id: number;
  /** Unit-sphere position, scaled by the scene at render time. */
  position: [number, number, number];
  /** [0.05, 0.95] — same bounds as the real belief_updater.py constants. */
  confidence: number;
  /** Live nodes render in Signal Amber, dormant nodes in grayscale — same
   * presence-of-color language as the Strategy Layer table. */
  live: boolean;
}

export interface BeliefEdge {
  a: number;
  b: number;
  /** Correlation strength, drives line thickness + particle flow speed. */
  strength: number;
}

// Mulberry32 — tiny deterministic PRNG, no external dependency.
function mulberry32(seed: number) {
  let a = seed;
  return function random() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Even distribution on a unit sphere — avoids the clumped-random look. */
function fibonacciSpherePoint(i: number, total: number): [number, number, number] {
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const y = 1 - (i / (total - 1)) * 2;
  const radiusAtY = Math.sqrt(1 - y * y);
  const theta = goldenAngle * i;
  return [Math.cos(theta) * radiusAtY, y, Math.sin(theta) * radiusAtY];
}

export function generateBeliefNetwork(
  nodeCount: number,
  seed = 42,
): { nodes: BeliefNode[]; edges: BeliefEdge[] } {
  const random = mulberry32(seed);

  const nodes: BeliefNode[] = Array.from({ length: nodeCount }, (_, i) => {
    // ~30% live (amber), rest dormant/frozen (grayscale) — matches the
    // real inventory's skew toward FROZEN/RESEARCH over LIVE.
    const live = random() < 0.3;
    const confidence = live
      ? 0.5 + random() * 0.45 // 0.50 - 0.95
      : 0.05 + random() * 0.35; // 0.05 - 0.40

    return {
      id: i,
      position: fibonacciSpherePoint(i, nodeCount),
      confidence: Math.min(0.95, Math.max(0.05, confidence)),
      live,
    };
  });

  // Each node connects to its 1-2 nearest neighbors by angle proximity —
  // reads as organic correlation structure, not a random hairball.
  const edges: BeliefEdge[] = [];
  const edgeKey = (a: number, b: number) => `${Math.min(a, b)}-${Math.max(a, b)}`;
  const seen = new Set<string>();

  for (let i = 0; i < nodes.length; i++) {
    const distances = nodes
      .map((n, j) => ({ j, d: j === i ? Infinity : distanceSq(nodes[i].position, n.position) }))
      .sort((a, b) => a.d - b.d);

    const neighborCount = 1 + Math.floor(random() * 2); // 1-2
    for (let k = 0; k < neighborCount; k++) {
      const j = distances[k].j;
      const key = edgeKey(i, j);
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push({ a: i, b: j, strength: 0.3 + random() * 0.7 });
    }
  }

  return { nodes, edges };
}

function distanceSq(a: [number, number, number], b: [number, number, number]) {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  const dz = a[2] - b[2];
  return dx * dx + dy * dy + dz * dz;
}
