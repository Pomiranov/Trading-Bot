import { mdxSource } from "./source.mdx";
import type { ContentSource } from "./types";

/**
 * The one line a future CMS migration touches. Every section component
 * imports `contentSource` from here, never `source.mdx` directly — swap in
 * a `source.sanity.ts` implementing the same ContentSource interface and
 * no page component changes.
 */
export const contentSource: ContentSource = mdxSource;

export * from "./types";
