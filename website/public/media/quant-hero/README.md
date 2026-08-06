# `public/media/quant-hero/`

Hero media for the Quant homepage. **This README is committed so the directory
exists in a fresh clone** — the video files themselves are not.

## What is in git

| File | In git | Notes |
|---|---|---|
| `hero-poster.avif` / `.webp` | ✅ yes | 1280×720. Generated, never extracted from video. |
| `hero-poster-mobile.avif` / `.webp` | ✅ yes | 768×432. Mark re-centred, not cropped. |
| `hero-prototype.mp4` | ❌ no | Local prototype only. |
| `hero-desktop.mp4` / `.webm` | ❌ no | Future production masters. |
| `hero-mobile.mp4` | ❌ no | Future production master. |

`*.mp4`, `*.webm` and `*.mov` under `public/media/` are gitignored — see
`website/.gitignore`.

## The site works without any video

If no video file is present, the `<video>` element never resolves a source and
the poster stays visible as the hero. No error, no layout shift, no build
failure. This is the expected state on CI, on Vercel, and after a fresh clone.

Check what you have:

```bash
npm run check:media
```

## Posters are drawn, not extracted

`hero-poster.*` are original brand graphics generated from
`scripts/media/build-poster.mjs`. They are **not** frames grabbed from the
prototype video, and contain no part of any third-party watermark.

Regenerate after changing the artwork:

```bash
npm run media:poster
```

## Watermark policy

The current prototype carries a burned-in provenance mark. It must never be
removed, cropped, covered, blurred, masked or overlaid. Read
[`docs/VIDEO_ASSET_GUIDE.md`](../../../docs/VIDEO_ASSET_GUIDE.md) before
touching framing, aspect ratio or `object-position`.
