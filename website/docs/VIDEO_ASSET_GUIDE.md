# VIDEO_ASSET_GUIDE.md — Quant hero media

**Status:** the hero video currently in use is a **local prototype, not a production master.**
It is not committed, and the site is built to render correctly without it.

---

## 1. Watermark and provenance policy

This section is normative. Read it before changing any framing value.

> **The visible watermark in the hero video must never be removed, cropped, covered, blurred, masked, or overlaid.** No CSS, transform, filter, mask, gradient, scaling, or aspect-ratio trick may be used to hide it. Framing values (`object-fit`, `object-position`, container aspect ratio) are chosen for composition only, and must be verified to keep the watermark region fully in frame.

### What that means operationally

The mark's position in the current prototype was measured, not assumed: it sits at
**x ≈ 88–94 %, y ≈ 86–92 %**, identical at t = 0.05 / 0.5 / 5.0 / 9.9 s.

With `object-fit: cover` and `object-position: 70% …`, the visible right edge of
the source is `896 + 0.3·W′` where `W′ = 1280 · aspect / 1.778`:

| Container aspect | Cropped | Right edge visible | Watermark | Q form |
|---|---|---|---|---|
| **16 / 9 = 1.778** | **0 %** | 1280 px | **intact** | **intact** |
| 3 / 2 = 1.500 | 15.6 % | 1220 px | intact (20 px margin) | intact |
| **1.41 — hard floor** | 21 % | 1200 px | exactly at the edge | intact |
| 4 / 3 = 1.333 | 25 % | 1184 px | **clipped** | marginal |
| 1 / 1 | 44 % | 1112 px | **clipped** | **clipped** |

**Rules that follow:**

1. `aspectRatio` defaults to **`16 / 9`** and must **never** go below **`1.41`**.
   At 16/9 the cover crop is a no-op, so nothing is cropped at all — this makes
   cropping out the mark structurally impossible rather than merely unintended.
2. `objectPosition: "70% 51%"` matches the measured subject centroid of the
   prototype. It is a composition choice, and at the default 16/9 it is inert.
   It is **not** a watermark measure and does not move the mark out of frame at
   any legal aspect ratio.
3. The readability overlay is **left-edge only** —
   `linear-gradient(to right, transparent 0%, #000 28%)`. 28 % lands inside the
   source's empty black band (x 0–35 %), so it touches no drawn content.
   **Bottom and right fades are forbidden**: the mark is 8–14 % from the bottom
   and 6–12 % from the right. If text is ever placed over the video, clamp the
   gradient to `x < 60 %`.
4. **Mobile does not crop.** The mobile container is also 16/9. To get a taller
   mobile block, re-author the poster artwork — never crop the frame.

### Provenance metadata

The prototype carries a **C2PA manifest** in an ISOBMFF `uuid` box
(`d8fec3d6-1b0e-483c-9297-5828877ec481`, 6,282 bytes), signed
*Google C2PA Media Services 1P ICA G3*, timestamped `2026-07-26T20:57:26Z`.

Be aware: **any transcode drops this box**, because `libx264` does not carry
ISOBMFF `uuid` boxes forward. That is a byproduct of re-encoding, not a
provenance-stripping measure. **Retain the untouched original locally**
alongside any derivative you create.

### Before a public release

The prototype must not reach a public build while it carries a visible mark.
Today this holds *by construction*: the `.mp4` is gitignored and the deployed
site renders poster-only. Shipping video publicly requires a **clean, licensed
master** — see §5.

---

## 2. The current prototype — measured facts

Source: `Create_a_premium_black_and_whi.mp4` (repo root, untracked)
Deployed to: `public/media/quant-hero/hero-prototype.mp4` (gitignored)

| Property | Value |
|---|---|
| Resolution | 1280 × 720 |
| Frame rate | **exactly 24.000 fps** (`stts` 240 samples × 512 @ timescale 12288) |
| Duration | 10.000 s |
| Video codec | H.264 High |
| Audio | AAC, 2 ch, 48 kHz, 128 kbps, 160,709 bytes |
| File size | 1,989,550 B (1.90 MiB) |
| Faststart | ✅ `moov` at byte 14,607, before `mdat` |
| Provenance | C2PA `uuid` box, 6,282 B |

**Composition:** the Q aperture spans x 42–88 %, y 15–90 %, centroid ≈ 70 % / 51 %.
The orange core peaks at **t = 6.0 s**. The **left third (x 0–35 %) is empty black
on every frame** — which is why the headline sits there.

**Known breach:** 1.90 MiB is **2.2× the 900 KB desktop budget** in §5. Accepted
for local prototyping only; a production master must meet the budget.

### The prototype does not loop

Mean luma by time:

| t (s) | 0.0 | 1.2 | 2.4 | 3.6 | 4.8 | 6.0 | 7.2 | 8.4 | 9.6 |
|---|---|---|---|---|---|---|---|---|---|
| luma /255 | **2.3** | 60.7 | 72.9 | 42.3 | 19.0 | 22.3 | 16.7 | 16.5 | 16.7 |

t = 0 is essentially pure black; t = 9.9 is a lit aperture. A plain `loop`
therefore produces a **hard black flash every 10 seconds**.

**Mitigation in use:** `HERO_MEDIA.loopRange = [6.4, 9.9]` in
`src/components/sections/hero/hero-media.ts`. `HeroVideo` seeks to `6.4 s` on
`loadedmetadata` and rewinds there on reaching `9.9 s`, giving a ~3.5 s window
across the settled range (mean luma 16.5–22.3). Mean luma is a coarse proxy —
**check the window visually after any asset change.**

**Proper fix:** the production master must be *authored* to loop, first frame
matching last. Then set `loopRange: undefined` and let the native `loop`
attribute do the work.

---

## 3. Rejected prototypes

Retained locally as references. **Never wire these to the page.**

| File | Size | Why rejected |
|---|---|---|
| `Create_a_black_and_white_abstr.mp4` | 2,312,271 B | Abstract motion with no brand read; would compete with the hero rather than support it. |
| `Create_a_premium_monochrome_D.mp4` | 2,564,928 B | Generic trading-dashboard footage. Weakens the brand against the real product UI, and risks reading as a fabricated product screenshot. |

Both are covered by the root `/*.mp4` gitignore rule. A future master must not
silently substitute either.

---

## 4. Posters — drawn, never extracted

`hero-poster.{avif,webp}` and `hero-poster-mobile.{avif,webp}` are **original
brand graphics**, generated by `scripts/media/build-poster.mjs` from the Quant
aperture geometry. They are **committed**.

```bash
npm run media:poster
```

**Why drawn rather than extracted — three reasons, in order of weight:**

1. **Licence and provenance.** An extracted frame would permanently commit
   AI-generated pixels *including the burned-in mark* into the repository as a
   production asset. A drawn poster avoids the question entirely.
2. **It survives the swap.** When the prototype is replaced by a licensed
   master, a poster extracted from the prototype becomes a *wrong* poster. A
   drawn one stays correct against any master sharing the brand composition.
3. **Size.** Measured: drawn AVIF **6.0 KB** vs an extracted frame at ~18 KB
   WebP — at an element that is a strong LCP candidate.

**This is not a watermark-removal measure.** The video is always played
byte-for-byte unmodified, mark included. Under reduced motion no video content
is shown at all — because *motion* is suppressed for accessibility, not because
the mark is being suppressed.

### Format choice, measured

WebP bottoms out around **11 KB** on this artwork even with the halo and guide
rings removed entirely — large near-black areas with antialiased edges are its
worst case, and lowering quality buys almost nothing while introducing visible
blocking. AVIF encodes the same image at roughly a third of that. So AVIF leads
and WebP is the fallback, selected by the browser via `<picture>`.

| File | Size | Budget |
|---|---|---|
| `hero-poster.avif` | 6.0 KB | 7 KB |
| `hero-poster.webp` | 15.5 KB | 16 KB |
| `hero-poster-mobile.avif` | 4.1 KB | 5 KB |
| `hero-poster-mobile.webp` | 8.1 KB | 9 KB |

The build script fails if any file exceeds its budget.

### Tooling notes — do not re-litigate these

Verified on this machine, so nobody wastes time rediscovering them:

- **`ffmpeg` / `ffprobe` are not installed.** `brew install ffmpeg` to get them.
- **`sips` cannot write WebP** — it is read-only in `sips --formats`.
- **`qlmanage -t` yields a black frame**, because t = 0 measures 2.3/255.
- **Playwright's bundled ffmpeg is useless here** — built `--disable-everything`,
  with no H.264 decoder and no mp4 demuxer.
- **`sharp` works** (0.34.5, librsvg 2.61.2, libwebp 1.6.0) but is an *optional*
  transitive dependency of `next`. `npm ci --omit=optional` drops it. If poster
  generation fails: `npm i -D sharp`.

### If you must extract a real frame anyway

Verified working, no ffmpeg required. Use **t = 6.0 s** (aperture fully formed,
orange core at peak). Never t < 1.0 s (black) or t ≈ 2.4 s (formless burst).
**The output will contain the burned-in mark, which must be left exactly as-is.**

```bash
cd website
swift - <<'SWIFT' | node -e '
const c=[];process.stdin.on("data",d=>c.push(d)).on("end",async()=>{
  await require("sharp")(Buffer.concat(c)).webp({quality:80,effort:6})
    .toFile("public/media/quant-hero/hero-poster.webp");
  console.log("wrote hero-poster.webp");
});'
import AVFoundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
let url = URL(fileURLWithPath: "../Create_a_premium_black_and_whi.mp4")
let gen = AVAssetImageGenerator(asset: AVURLAsset(url: url))
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter  = .zero
let cg = try gen.copyCGImage(at: CMTime(seconds: 6.0, preferredTimescale: 600), actualTime: nil)
let data = NSMutableData()
let dest = CGImageDestinationCreateWithData(data, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, cg, nil)
CGImageDestinationFinalize(dest)
FileHandle.standardOutput.write(data as Data)
SWIFT
```

---

## 5. Required production assets

| File | Res | fps | Codec | Bitrate | Budget | Audio | Duration |
|---|---|---|---|---|---|---|---|
| `hero-desktop.mp4` | 1280×720 | 24 | H.264 High L4.0, yuv420p, faststart | ~700 kbps | **≤ 900 KB** | none (`-an`) | 8–10 s, seamless loop |
| `hero-desktop.webm` | 1280×720 | 24 | VP9, yuv420p | ~500 kbps | **≤ 650 KB** | none | same |
| `hero-mobile.mp4` | 768×432 | 24 | H.264 High L3.1, yuv420p, faststart | ~280 kbps | **≤ 350 KB** | none | same |
| `hero-poster.avif` / `.webp` | 1280×720 | — | AVIF q50 / WebP q72 | — | 7 KB / 16 KB | — | — |
| `hero-poster-mobile.avif` / `.webp` | 768×432 | — | AVIF q50 / WebP q72 | — | 5 KB / 9 KB | — | — |

1280×720 is not a downgrade: the hero panel is ≤ ~640 CSS px wide, so at 2× DPR
1280 is already the correct native size and upscaling would be wasted bytes.

**Audio must be stripped (`-an`).** The prototype does carry an AAC stereo
track; whether it is silent could not be verified locally. Removing it makes the
question moot, reclaims ~160 KB, and guarantees nothing can ever un-mute.

---

## 6. Encoding commands

Run once `ffmpeg` is installed (`brew install ffmpeg`).

```bash
# Desktop H.264
ffmpeg -i hero-master.mov \
  -an -sn -dn \
  -vf "scale=1280:720:flags=lanczos,format=yuv420p" \
  -c:v libx264 -profile:v high -level:v 4.0 \
  -crf 25 -preset slower \
  -g 48 -keyint_min 48 -sc_threshold 0 \
  -x264-params "ref=4:bframes=3:aq-mode=3" \
  -movflags +faststart \
  public/media/quant-hero/hero-desktop.mp4

# Mobile H.264
ffmpeg -i hero-master.mov \
  -an -sn -dn \
  -vf "scale=768:432:flags=lanczos,format=yuv420p" \
  -c:v libx264 -profile:v high -level:v 3.1 \
  -crf 28 -preset slower \
  -g 48 -keyint_min 48 -sc_threshold 0 \
  -movflags +faststart \
  public/media/quant-hero/hero-mobile.mp4

# Desktop VP9 / WebM
ffmpeg -i hero-master.mov \
  -an -sn -dn \
  -vf "scale=1280:720:flags=lanczos,format=yuv420p" \
  -c:v libvpx-vp9 -crf 34 -b:v 0 \
  -row-mt 1 -tile-columns 2 -threads 8 \
  -g 48 -deadline good -cpu-used 2 \
  -auto-alt-ref 1 -lag-in-frames 25 \
  public/media/quant-hero/hero-desktop.webm

# Verify against budget
for f in public/media/quant-hero/hero-*.mp4 public/media/quant-hero/hero-*.webm; do
  ffprobe -v error -show_entries format=size,duration,bit_rate \
          -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames \
          -of default=noprint_wrappers=1 "$f"
done
```

**Tuning:** over budget → raise `-crf` by 2 and re-measure. Visibly banded in
the dark gradients (likely — the content is ~90 % near-black) → lower `-crf`, or
prefer `-tune grain` over raising bitrate globally. `-g 48` (a 2 s GOP at 24 fps)
with `-sc_threshold 0` keeps a keyframe at t = 0 so loop restarts are instant.

Poster export once ffmpeg exists (the drawn poster in §4 remains canonical):

```bash
ffmpeg -ss 6.000 -i hero-master.mov -frames:v 1 \
  -vf "scale=1280:720:flags=lanczos" \
  -c:v libwebp -lossless 0 -quality 80 -compression_level 6 -preset picture \
  public/media/quant-hero/hero-poster.webp
```

---

## 7. Swapping in a new asset

The component reads every path from one object, so a swap is a one-file edit.

1. Drop the new files into `public/media/quant-hero/` using **new,
   version-suffixed filenames** — e.g. `hero-desktop.v2.mp4`. This is required:
   `/media/*` is served `immutable` (see `next.config.ts` `headers()`), so a
   reused filename will be served from cache indefinitely.
2. Edit **only** `HERO_MEDIA` in
   `src/components/sections/hero/hero-media.ts`.
3. If the composition changed, re-run `npm run media:poster`.
4. If the new master loops seamlessly, set `loopRange: undefined`.
5. `npm run check:media`
6. **Re-measure the watermark position on the new asset** — do not assume it
   matches the prototype's — and re-verify the §1 framing table against it.
7. Run the QA checklist in `SITE_REDESIGN_PLAN.md` §10, including the
   absent-file test (rename the mp4 away, rebuild, confirm the poster is the LCP
   element and CLS is unchanged).

---

## 8. Open items

- **Audio content unverified.** The prototype has an AAC track; no local decoder
  outputs PCM without writing a file. Production encodes strip audio regardless.
- **`sharp` is an optional dep** of `next` — see §4 tooling notes.
- **AVIF for video** (`-c:v libsvtav1 -crf 38 -preset 6`) deferred pending a
  Safari coverage assessment. AVIF is already used for the *posters*.
- **The 404-advances-to-next-`<source>` behaviour** that the poster-only
  fallback relies on is spec-derived; the absent-file test in §7 step 7 is what
  confirms it empirically.
