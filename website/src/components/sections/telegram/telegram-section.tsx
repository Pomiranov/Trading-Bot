import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";
import { MonoLabel } from "@/components/ui/mono-label";
import { Surface } from "@/components/ui/surface";
import { Reveal } from "@/components/motion/reveal";
import { SignalCard } from "./signal-card";

/**
 * Telegram as a touchpoint, not a chapter.
 *
 * ── What this used to be, and why it is now a fraction of the size ──
 *
 * A full section: eyebrow, H2, lead, four feature cards in a hairline-separated
 * list, and the signal card inside a phone frame. Measured at 950px tall on
 * desktop, arriving immediately after the 822px dashboard section that makes the
 * *same* argument about the *same* shared state.
 *
 * By this point a reader has been told twice that Telegram and the dashboard read
 * one state. The four features restated it a third time in four more paragraphs —
 * "Синхронизация: Dashboard и бот читают одни и те же репозитории" is the section
 * lead with a heading on it. That is the essay text this pass was asked to
 * remove.
 *
 * So it keeps exactly one idea, which was always the only one that mattered:
 * **Telegram is a second interface onto the same state, not a simplified copy.**
 * Everything else was elaboration.
 *
 * ── Composition ──
 *
 * One card, two halves: the claim on the left, the genuinely pressable signal
 * card on the right.
 *
 *   • The `DeviceFrame` bezel is gone. It spent ~90px of chrome saying "this is a
 *     phone" about a card whose content already says so, and its clip was
 *     truncating the demo hint underneath — visible in the before-shot as text
 *     running under the frame's edge.
 *   • The H2 is rendered directly rather than through `SectionHeader`, because a
 *     touchpoint carrying an eyebrow, a heading, a lead *and* a note is not a
 *     touchpoint. It keeps its `{id}-heading` id, so `Section`'s
 *     `aria-labelledby` still resolves — that contract is not optional.
 *
 * ── Do not regress the card to a mock ──
 *
 * `SignalCard` stays a client component so its two buttons can genuinely be
 * pressed. A previous version drew `aria-hidden` <span>s styled to look like
 * controls, which is exactly the "raw" impression this section was corrected for.
 */
export async function TelegramSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "telegram" });

  return (
    // `tight` and it stays: Telegram is the second interface onto the *same
    // state* as the dashboard above, so the two belong to one movement. The
    // divider is what keeps them distinct without adding a full section gap.
    <Section id="telegram" rhythm="tight" divider>
      <Reveal lift={false}>
        {/*
          `interactive={false}` + `panel-bloom` — the operator terminal's route,
          for the same reason it exists there. Measured at 1440 this block is
          1204×439, a 3286px perimeter, almost exactly twice the next largest
          card on the page, where every other card sits in a 1290–1822px band.
          Left on the card primitive it was the page's largest hoverable object
          *and* the only panel-sized surface still taking `.card-premium`'s -6px
          lift — an object this size sliding under the cursor reads as the page
          wobbling, not as elevation, which is exactly why the terminal opts out.

          `.panel-bloom` keeps everything the lift is not: border highlight,
          background step and the rim, at the panel scale (`--rim-*-panel`) —
          the quietest of the three, the same scale `card-premium--panel`
          selected before. At the ordinary card intensity a ring that long reads
          as a lit sign rather than as a panel acknowledging the pointer, and
          this block must not out-shout the hero. Its own signal card inside
          keeps the card scale, so the pair still has a hierarchy.
        */}
        <Surface
          variant="raised"
          padding="lg"
          interactive={false}
          className="panel-bloom grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)] lg:gap-14"
        >
          <div className="flex min-w-0 flex-col gap-4">
            <MonoLabel>{t("eyebrow")}</MonoLabel>
            <SectionHeading id="telegram-heading" className="max-w-[24ch]">
              {t("heading")}
            </SectionHeading>
            <p className="max-w-[52ch] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] tracking-[var(--text-lead--letter-spacing)] text-[color:var(--color-text-secondary)]">
              {t("lead")}
            </p>
          </div>

          {/* The artefact, at its own size. `min-w-0` so the card's mono labels
              shrink rather than pushing the grid wider than its column — this is
              the one place on the page where a fixed-width child could produce
              horizontal overflow at 320px. */}
          <div className="min-w-0">
            <SignalCard />
          </div>
        </Surface>
      </Reveal>
    </Section>
  );
}
