"use client";

import { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { track } from "@/lib/analytics/events";

interface NavLink {
  key: string;
  label: string;
  href: string;
}

export function MobileNav({
  links,
  ctaLabel,
  localeSwitchLabel,
  localeSwitchHref,
  openLabel,
  closeLabel,
}: {
  links: NavLink[];
  ctaLabel: string;
  localeSwitchLabel: string;
  localeSwitchHref: string;
  openLabel: string;
  closeLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();

  function close() {
    setOpen(false);
  }

  return (
    <>
      {/* Hamburger toggle */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? closeLabel : openLabel}
        className="relative flex size-11 flex-col items-center justify-center gap-[5.5px] rounded-[var(--radius-md)] border transition-colors duration-[var(--duration-base)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)] lg:hidden"
        style={{
          background: open ? "var(--color-highlight-bg)" : "var(--color-fill-subtle)",
          borderColor: open ? "var(--color-highlight-border)" : "var(--color-border-strong)",
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block h-px w-[14px] rounded-full transition-all duration-300 origin-center"
            style={{
              background: open ? "var(--color-accent)" : "var(--color-text-secondary)",
              opacity: i === 1 && open ? 0 : 1,
              transform:
                open
                  ? i === 0
                    ? "translateY(5.5px) rotate(45deg)"
                    : i === 2
                    ? "translateY(-5.5px) rotate(-45deg)"
                    : "none"
                  : "none",
            }}
          />
        ))}
      </button>

      <AnimatePresence>
        {open && (
          <>
            {/* Tap-outside backdrop */}
            <motion.div
              key="backdrop"
              className="fixed inset-0"
              style={{ zIndex: "calc(var(--z-nav) - 2)" }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={close}
              aria-hidden="true"
            />

            {/* Dropdown panel */}
            <motion.nav
              key="panel"
              aria-label="Navigation"
              className="fixed left-4 right-4 top-[var(--nav-panel-top)] lg:hidden overflow-hidden rounded-[var(--radius-xl)]"
              style={{
                zIndex: "calc(var(--z-nav) - 1)",
                background: "var(--color-glass-surface-strong)",
                backdropFilter: "blur(32px)",
                WebkitBackdropFilter: "blur(32px)",
                border: "1px solid var(--color-glass-border)",
                boxShadow: "var(--shadow-nav-panel)",
              }}
              initial={reduce ? false : { opacity: 0, y: -8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              {/* Nav links */}
              <div className="flex flex-col p-3 gap-0.5">
                {links.map(({ key, label, href }, i) => (
                  <motion.a
                    key={key}
                    href={href}
                    onClick={() => {
                      track({ name: "journey_step", props: { section: key } });
                      close();
                    }}
                    className="flex items-center rounded-[var(--radius-md)] px-3 py-3 font-mono text-[length:var(--text-caption)] tracking-[0.1em] text-[color:var(--color-text-secondary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:bg-[color:var(--color-highlight-bg)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
                    initial={reduce ? false : { opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{
                      duration: 0.2,
                      delay: 0.05 + i * 0.04,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                  >
                    {label}
                  </motion.a>
                ))}
              </div>

              {/* Divider */}
              <div
                className="mx-3"
                style={{ height: "1px", background: "var(--color-border)" }}
              />

              {/* Bottom row: locale switch + CTA */}
              <div className="flex items-center justify-between gap-3 p-3">
                <a
                  href={localeSwitchHref}
                  onClick={close}
                  className="rounded-[var(--radius-md)] border border-[color:var(--color-border-strong)] px-3 py-2.5 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-secondary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] hover:text-[color:var(--color-text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
                >
                  {localeSwitchLabel}
                </a>
                <a
                  href="#access"
                  onClick={() => {
                    track({ name: "cta_clicked", props: { target: "sandbox_access", location: "mobile_nav" } });
                    close();
                  }}
                  className="rounded-[var(--radius-md)] bg-[color:var(--color-accent)] px-5 py-2.5 font-mono text-[length:var(--text-caption)] font-semibold tracking-[0.1em] text-[color:var(--color-bg)] uppercase no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
                >
                  {ctaLabel}
                </a>
              </div>
            </motion.nav>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
