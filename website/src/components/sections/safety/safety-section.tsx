import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { MonoLabel } from "@/components/ui/mono-label";
import { Reveal } from "@/components/motion/reveal";

/**
 * The section that matters most, because Quant can place orders in someone's
 * brokerage account.
 *
 * Every claim here is backed by code, and the places where the guarantee is
 * *incomplete* are stated rather than omitted:
 *
 *   item4  — there is no automatic kill switch. Drawdown is alert-only
 *            (bot/ui/telegram_bot.py:860); the stop is manual
 *            (bot/services/bot_engine.py:91-102).
 *   item6  — confidence is clamped to 0.05–0.95 and never becomes certainty.
 *
 * A third disclosure — that the credential vault is opt-in via
 * SECRETS_MASTER_KEY and falls back to a plain `.env` without it — used to sit
 * below the limits group and now lives in the deployment documentation. See the
 * note where it was, at the foot of this file, for why, and for the one rewrite
 * of this section that would be dishonest.
 *
 * The strongest claim is item1, and it is verified by absence: BrokerAdapter
 * (bot/broker/base.py:141-219) declares no withdraw or transfer method at all.
 *
 * ── Why the six cards are now two groups ──
 *
 * They used to be one uniform `md:2 lg:3` grid, which meant the two items that
 * describe *limits* looked exactly like the four that describe reassurances.
 * The honesty was present in the copy and invisible in the design — and on a
 * page about letting software touch a brokerage account, the caveats are the
 * differentiator and the part most worth reading.
 *
 * So they are split, and the limits group is deliberately given *more* weight:
 * a raised surface, wider cards, larger padding, a left rule, body copy at full
 * primary contrast rather than secondary, and the vault caveat beneath it in
 * the `caveat` tone. These must never be softened or equalised upward.
 */
const GUARANTEES = ["item1", "item2", "item3", "item5"] as const;
const LIMITS = ["item4", "item6"] as const;

export async function SafetySection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "safety" });

  return (
    <Section id="safety" rhythm="default" divider>
      <SectionHeader id="safety" eyebrow={t("eyebrow")} heading={t("heading")} lead={t("lead")} />

      {/* ── Guarantees ──
          The two group labels are <h3>s (and the card titles <h4>s under them):
          the guarantees/limits split *is* this section's argument, and as plain
          <p>s it had no structure in the accessibility tree — a screen-reader
          user could not tell where the reassurances end and the caveats begin.
          MonoLabel's `as` keeps the visual treatment identical. */}
      <div className="mt-[var(--space-header-to-body)] flex flex-col gap-5">
        <MonoLabel as="h3">{t("guaranteesHeading")}</MonoLabel>
        {/*
          Two columns at every width from `sm`, not four at `lg`.

          The four-up row equalised to its tallest card, and these four bodies are
          not the same length: `item5` carries the encryption claim plus its
          master-key qualifier — roughly three times `item3`'s copy. Measured at
          1440 the row was 414px tall and the slack at the foot of each card ran
          108 / 161 / **187** / 29px, so three of the four guarantees on the page's
          most important section ended in a third of a card of empty panel.

          Two columns fixes it from both ends: the longest body gets 591px of
          measure instead of 283px, so it is roughly half as tall to begin with,
          and it now equalises against `item3` alone rather than setting the height
          of all four. Worst-case slack drops to ~106px.

          It also agrees with the audience grid, which stops at two columns for the
          same reason and says so — a 4-up at `lg` puts Russian bodies back into
          ~300px columns.
        */}
        <ul className="grid gap-[var(--space-card-gap)] sm:grid-cols-2">
          {GUARANTEES.map((item, i) => (
            <li key={item} className="flex">
              <Reveal index={i} className="flex w-full">
                <Surface padding="md" className="flex w-full flex-col gap-3">
                  {/* <h4>, one level under the group's <h3> label above. */}
                  <h4 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {t(`${item}Title`)}
                  </h4>
                  <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                    {t(`${item}Body`)}
                  </p>
                </Surface>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>

      {/* ── Where the guarantee stops ──
          Two cards spanning the width the four above occupy, raised, with more
          padding. Heavier than the guarantees, on purpose.

          ── The 2px left rule is gone, and it was a real defect ──

          It was `border-l-2` with an inline `borderLeftColor:
          var(--color-text-secondary)` — a 2px bar at 72% white down one edge of
          a graphite card, permanently. Rendered at 1440 it is the single
          brightest line in the section, and because the other three edges are
          `--color-border` at 10% it reads as an *asymmetry*: a one-sided white
          stripe, which is what a clipped border or a stray focus ring looks
          like. The owner's review named it exactly that, and required a uniform
          hairline all the way round.

          Emphasis is not lost, because the rule was one of five devices and the
          other four are untouched: a raised surface, `lg` padding, two cards
          spanning the width the four guarantees occupy, and body copy at primary
          rather than secondary contrast. `--color-border-strong` on all four
          edges keeps a *sixth* — these cards have a visibly firmer outline than
          the guarantees above them — without putting the weight on one side.

          `card-neutral` is the other half, and it carries both changes. It must
          not be an inline style: an inline `borderColor` beats *every* stylesheet
          rule short of `!important`, which is precisely how the old left rule
          "survived hover" — and a resting edge that cannot lighten is the
          asymmetry problem again in a different form. As a class in globals.css
          it loses to `.card-premium:hover` on specificity, so the edge resolves
          to the same highlight white every other card on the page uses.

          The class also stops these two taking the cold rim the rest of the
          page's cards light on hover: blue is a signal colour and these are
          statements of limitation. See `--rim-*-neutral` in tokens/color.css. */}
      <div className="mt-[var(--space-block)] flex flex-col gap-5">
        <MonoLabel as="h3">{t("limitsHeading")}</MonoLabel>
        <ul className="grid gap-[var(--space-card-gap)] md:grid-cols-2">
          {LIMITS.map((item, i) => (
            <li key={item} className="flex">
              <Reveal index={i} className="flex w-full">
                <Surface
                  variant="raised"
                  padding="lg"
                  className="card-neutral flex w-full flex-col gap-3"
                >
                  {/* <h4>, one level under the group's <h3> label above. */}
                  <h4 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {t(`${item}Title`)}
                  </h4>
                  <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-primary)]">
                    {t(`${item}Body`)}
                  </p>
                </Surface>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>

      {/*
        ── Removed: the credential-vault caveat ──

        `keysCaveat` read, in full: storage encryption is switched on by a master
        key; if it is not set at deploy time credentials stay in a plain `.env`,
        which is the default for a local install and must be changed before going
        live.

        That is true (bot/security/credential_store.py:50-57) and it is a
        deployment note. It was the longest piece of small print on the page, it
        described the operator's own server configuration rather than anything
        Quant does to a visitor, and it sat in the section a prospect reads to
        decide whether this is safe at all. Owner direction: it belongs in the
        deployment documentation.

        ── The condition moved into item5, it was not dropped ──

        This is the part that nearly went wrong, and it is why the caveat cannot
        simply be deleted.

        `item5` already claimed "Ключи брокера хранятся зашифрованными
        (AES-256-GCM)…", and the caveat below was what *qualified* it. Removing
        the caveat on its own would therefore have turned a conditional statement
        into an unconditional one — a stronger claim than the code supports, from
        a deletion. Caught on review of the rendered section, not in the diff.

        So the condition is now a clause inside item5 itself: encryption is
        switched on by a master key at deployment. One clause instead of a
        four-line block, which is what "honest but concise" has to mean here.

        `item5` may not be reverted to an unqualified encryption claim. If the
        vault ever becomes non-optional, `bot/security/credential_store.py` is the
        file that decides, and this copy changes with it.

        ── What was NOT weakened ──

        The two guarantees that are unconditional stay exactly as they were, in
        the `limits` group above, at more weight than the reassurances:

          • item4 — there is no automatic kill switch; drawdown is alert-only and
            the stop is manual (bot/ui/telegram_bot.py:860,
            bot/services/bot_engine.py:91-102)
          • item6 — confidence is clamped to 0.05–0.95 and never becomes certainty

        And the strongest claim on the site is unaffected, because it is verified
        by absence: `BrokerAdapter` (bot/broker/base.py:141-219) declares no
        withdraw or transfer method at all.

        If a reviewer wants the vault caveat visible on the landing page again,
        that is a copy decision — but it may not be replaced with "keys are
        encrypted" full stop, which is the one rewrite that would be false.
      */}
    </Section>
  );
}
