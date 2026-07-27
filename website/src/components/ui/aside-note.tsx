import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

interface AsideNoteProps extends ComponentPropsWithoutRef<"div"> {
  /**
   * `caveat` is visually heavier than `default`.
   *
   * This exists because of a specific problem in the safety section: two of its
   * six items state where the guarantee is *incomplete* (there is no automatic
   * kill switch; the credential vault is opt-in), and they were rendered
   * identically to the four reassuring ones. The honesty was present in the
   * copy and invisible in the design.
   *
   * The caveats are the differentiator on a page about letting software touch a
   * brokerage account. They get more weight, never less.
   */
  tone?: "default" | "caveat";
  size?: "body" | "caption";
}

/**
 * A note set off by a left rule.
 *
 * The `border-l-2 pl-5` pattern appeared five times across the page —
 * how-it-works twice, safety, strategies, access — with no shared component and
 * three different type sizes between them. This is that pattern, once.
 */
export function AsideNote({
  tone = "default",
  size = "body",
  className,
  children,
  ...props
}: AsideNoteProps) {
  return (
    <div
      className={cn(
        "border-l-2 pl-5",
        tone === "caveat"
          ? "border-[color:var(--color-text-secondary)] text-[color:var(--color-text-primary)]"
          : "border-[color:var(--color-border-strong)] text-[color:var(--color-text-secondary)]",
        size === "body"
          ? "text-[length:var(--text-body)] leading-[var(--text-body--line-height)]"
          : "text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
