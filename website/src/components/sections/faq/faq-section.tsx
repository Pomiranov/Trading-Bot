"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";

function FaqItem({ q, a, index }: { q: string; a: string; index: number }) {
  const [open, setOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
      style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center justify-between gap-4 py-5 text-left"
        style={{ background: "none", border: "none", outline: "none" }}
      >
        <span
          className="font-medium text-[15px] leading-snug transition-colors duration-200"
          style={{
            color: open ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.75)",
            letterSpacing: "-0.01em",
          }}
        >
          {q}
        </span>
        <span
          className="flex size-6 shrink-0 items-center justify-center rounded-md transition-all duration-300"
          style={{
            background: open ? "rgba(255,138,30,0.12)" : "rgba(255,255,255,0.04)",
            border: `1px solid ${open ? "rgba(255,138,30,0.2)" : "rgba(255,255,255,0.07)"}`,
            color: open ? "var(--color-accent)" : "rgba(255,255,255,0.3)",
            transform: open ? "rotate(45deg)" : "rotate(0deg)",
            fontSize: "16px",
            fontFamily: "var(--font-mono)",
            lineHeight: 1,
          }}
          aria-hidden="true"
        >
          +
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="answer"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            style={{ overflow: "hidden" }}
          >
            <p
              className="pb-5 max-w-[62ch] text-[15px] leading-relaxed"
              style={{ color: "rgba(255,255,255,0.62)" }}
            >
              {a}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function FaqSection() {
  const t = useTranslations("faq");

  const items = [1, 2, 3, 4, 5].map((n) => ({
    q: t(`q${n}` as "q1"),
    a: t(`a${n}` as "a1"),
  }));

  return (
    <section
      id="faq-section"
      aria-labelledby="faq-heading"
      className="px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <div className="mx-auto flex max-w-[760px] flex-col gap-10">
        <div>
          <h2
            id="faq-heading"
            style={{
              fontSize: "var(--text-section-heading)",
              lineHeight: "var(--text-section-heading--line-height)",
              letterSpacing: "var(--text-section-heading--letter-spacing)",
              fontWeight: 500,
              color: "var(--color-text-primary)",
            }}
          >
            {t("heading")}
          </h2>
        </div>

        <div className="flex flex-col">
          {items.map((item, i) => (
            <FaqItem key={item.q} q={item.q} a={item.a} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
