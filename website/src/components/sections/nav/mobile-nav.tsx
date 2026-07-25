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
        className="relative flex lg:hidden size-9 flex-col items-center justify-center gap-[5.5px] rounded-lg transition-colors duration-200"
        style={{
          background: open ? "rgba(255,138,30,0.08)" : "rgba(255,255,255,0.04)",
          border: `1px solid ${open ? "rgba(255,138,30,0.22)" : "rgba(255,255,255,0.07)"}`,
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block h-px w-[14px] rounded-full transition-all duration-300 origin-center"
            style={{
              background: open ? "var(--color-accent)" : "rgba(255,255,255,0.6)",
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
              className="fixed left-4 right-4 top-[68px] lg:hidden overflow-hidden rounded-xl"
              style={{
                zIndex: "calc(var(--z-nav) - 1)",
                background: "rgba(7,7,9,0.96)",
                backdropFilter: "blur(32px)",
                WebkitBackdropFilter: "blur(32px)",
                border: "1px solid rgba(255,255,255,0.09)",
                boxShadow:
                  "0 8px 48px rgba(0,0,0,0.6), 0 2px 8px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
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
                    className="flex items-center rounded-lg px-3 py-3 font-mono text-[12px] uppercase tracking-[0.1em] transition-colors duration-150"
                    style={{ color: "rgba(255,255,255,0.55)", textDecoration: "none" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                      e.currentTarget.style.color = "rgba(255,255,255,0.9)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "";
                      e.currentTarget.style.color = "rgba(255,255,255,0.55)";
                    }}
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
                style={{ height: "1px", background: "rgba(255,255,255,0.06)" }}
              />

              {/* Bottom row: locale switch + CTA */}
              <div className="flex items-center justify-between gap-3 p-3">
                <a
                  href={localeSwitchHref}
                  onClick={close}
                  className="font-mono text-[11px] uppercase tracking-[0.12em] rounded-lg px-3 py-2 transition-colors duration-150"
                  style={{
                    color: "rgba(255,255,255,0.3)",
                    textDecoration: "none",
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  {localeSwitchLabel}
                </a>
                <a
                  href="#cta-heading"
                  onClick={() => {
                    track({ name: "cta_clicked", props: { target: "beta_form", location: "mobile_nav" } });
                    close();
                  }}
                  className="font-mono text-[12px] uppercase tracking-[0.1em] rounded-lg px-5 py-2.5 transition-all duration-200"
                  style={{
                    background: "linear-gradient(135deg, #ff8a1e 0%, #d96a12 100%)",
                    color: "#040404",
                    fontWeight: 600,
                    textDecoration: "none",
                    boxShadow: "0 0 0 1px rgba(255,138,30,0.25), 0 4px 16px rgba(255,138,30,0.18)",
                  }}
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
