import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { compileMDX } from "next-mdx-remote/rsc";
import type {
  ContentSource,
  LearningSystemCopy,
  PhilosophyBlock,
  PipelineStage,
  StrategyRecord,
} from "./types";

const CONTENT_ROOT = path.join(process.cwd(), "content");

async function readMdxDir<Frontmatter extends { order: number }>(
  locale: string,
  dir: string,
) {
  const dirPath = path.join(CONTENT_ROOT, locale, dir);
  const files = (await readdir(dirPath)).filter((f) => f.endsWith(".mdx"));

  const entries = await Promise.all(
    files.map(async (file) => {
      const raw = await readFile(path.join(dirPath, file), "utf8");
      const { content, frontmatter } = await compileMDX<Frontmatter>({
        source: raw,
        options: { parseFrontmatter: true },
      });
      return { content, frontmatter, file };
    }),
  );

  return entries.sort((a, b) => a.frontmatter.order - b.frontmatter.order);
}

async function getPipelineStages(locale: string): Promise<PipelineStage[]> {
  const entries = await readMdxDir<{
    id: PipelineStage["id"];
    order: number;
    title: string;
    sourceRef?: string;
  }>(locale, "engine-pipeline");

  return entries.map(({ content, frontmatter }) => ({
    id: frontmatter.id,
    order: frontmatter.order,
    title: frontmatter.title,
    sourceRef: frontmatter.sourceRef,
    description: content,
  }));
}

async function getStrategies(locale: string): Promise<StrategyRecord[]> {
  const raw = await readFile(
    path.join(CONTENT_ROOT, locale, "strategies.json"),
    "utf8",
  );
  return JSON.parse(raw) as StrategyRecord[];
}

async function getPhilosophyBlocks(locale: string): Promise<PhilosophyBlock[]> {
  const entries = await readMdxDir<{ id: string; order: number; heading: string }>(
    locale,
    "philosophy",
  );

  return entries.map(({ content, frontmatter }) => ({
    id: frontmatter.id,
    heading: frontmatter.heading,
    body: content,
  }));
}

async function getLearningSystemCopy(locale: string): Promise<LearningSystemCopy> {
  const raw = await readFile(
    path.join(CONTENT_ROOT, locale, "learning-system.mdx"),
    "utf8",
  );
  const { content, frontmatter } = await compileMDX<{
    sliderCaption: string;
    minTradesFloor: number;
    minConfidence: number;
    maxConfidence: number;
  }>({ source: raw, options: { parseFrontmatter: true } });

  return {
    intro: content,
    sliderCaption: frontmatter.sliderCaption,
    minTradesFloor: frontmatter.minTradesFloor,
    minConfidence: frontmatter.minConfidence,
    maxConfidence: frontmatter.maxConfidence,
  };
}

export const mdxSource: ContentSource = {
  getPipelineStages,
  getStrategies,
  getPhilosophyBlocks,
  getLearningSystemCopy,
};
