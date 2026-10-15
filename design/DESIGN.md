# Vouch design spec: Exhibit

Binding for every surface a judge sees: the web feed, the claim page, the
record of reliance, the README, the cover and thumbnail, the deck, the gallery
images and the video cards. Subomi picked direction E, Exhibit, on 15 Oct 2026
from [`directions-2.html`](directions-2.html). The earlier rounds
([`directions.html`](directions.html)) are kept for reference only.

Audience: lawyers, compliance officers, and a few Web3 and sponsor judges. They
handle exhibits, evidence and chain-of-custody forms every week. Exhibit makes
each claim one of those objects. The frame is loud: a manila folder, a yellow
sticker, tape and stamps. The evidence is plain: typed words at full contrast.

## 1. The objects, and what each one means

Every object stands for something real in the product. Nothing is decoration.

| Object | Means | Where |
|---|---|---|
| **Manila folder** with tabs | A case: one company's filing. The tabs are the tickers | The page background; the ticker filter |
| **Evidence tape** | The frame. "EVIDENCE · DO NOT TAMPER": the claim's words are hashed on-chain | The top edge of the folder, the cover, the video cards. Never over text |
| **Exhibit sticker** (yellow) | One claim, numbered by its on-chain claim id | The claim record, the claims list, the thumbnail |
| **Claim record** (white typed form) | The claim, its source and the check | The hero screen |
| **Stamp** | The verdict: SLASHED (red), CLEARED (blue), UNCHECKED (grey, dashed) | On the form's frame, beside the evidence, never over it |
| **Red ring** | The exact wrong words in a claim | Inside the typed statement |
| **Yellow marker** | The filing's sentence that the claim cites | Inside the source quotation |
| **Chain-of-custody form** | The record of reliance: every hand the claim passed through | Under the claim, in the journal, the printable record |

## 2. Principles (testable)

1. **The evidence is one click away.** Any screen that shows a claim shows, or
   links in one click to, the filing sentence it cites, with the SEC accession
   number. Test: from any claim, the filing sentence and the accession number
   are reachable in one click.
2. **One verdict vocabulary.** Cleared, Slashed, Unchecked, each with a
   one-line plain reason ("wrong quarter", "a figure was changed"). Never TRUE,
   WRONG, PASS, FAIL or emoji. Test: search the rendered text.
3. **Stamps and tape frame the evidence and never cover it.** A stamp may
   overlap the form's margin or border, never the typed statement, the filing
   sentence or the findings. The tape never crosses text. Test: at 390 px and
   1440 px, the bounding box of every stamp and tape strip intersects no
   quotation or findings box.
4. **Red means Slashed or a wrong word.** Nothing else on any surface is red:
   no red buttons, links, tape, headings or decorations. Test: every red
   element is a Slashed stamp, a Slashed label, or a ringed wrong word.
5. **The typed statement and the filing sentence stay at full contrast.**
   They are set in ink on paper (18.9:1, 13.5:1 dark), or ink on the yellow
   marker (13.2:1). No opacity, no texture, no overlay on them. Test: computed
   colour of both is `--ink` (or `--onyellow` inside the marker) with
   opacity 1.
6. **Hashes are fine print.** Transaction ids, hashes and addresses are
   Courier Prime at most 13 px, truncated in the middle (`0xbed0273d…12892`),
   in the record fields or the chain of custody, never in a heading, button or
   stamp. Test: no hex string larger than 13 px.
7. **One name, one place.** The product name comes from `web/brand.js` (and
   `design/assets/brand.json` for the generated assets). Test: renaming is a
   one-line change and a rebuild.

## 3. Tokens

### Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| `--manila` | `#E9D5A4` | `#1B1813` | page (the folder) |
| `--tab` | `#D9BE80` | `#3A3226` | folder tabs, quiet panels on the folder |
| `--paper` | `#FFFFFF` | `#26221B` | the typed forms |
| `--ink` | `#111111` | `#F3ECDD` | text, rules, buttons |
| `--ink2` | `#4A4234` | `#C3B8A2` | labels, metadata, the Unchecked stamp |
| `--faint` | `#D8CDB6` | `#4A4234` | hairlines on the form (never text) |
| `--yellow` / `--onyellow` | `#FFD400` / `#111111` | same | exhibit sticker, the filing marker, the tape lettering |
| `--tape` / `--ontape` | `#111111` / `#FFD400` | `#FFD400` / `#111111` | evidence tape |
| `--red` / `--redwash` | `#C8102E` / `#FBE7E9` | `#FF6B5E` / `#3A1F1C` | Slashed and the wrong words only |
| `--blue` / `--bluewash` | `#1D3FA6` / `#E8ECF8` | `#8EA6FF` / `#232A40` | Cleared stamp ink only |

Contrast, WCAG 2 formula, text on background:

| Pair | Light | Dark | Note |
|---|---|---|---|
| ink on manila | 13.1 | 15.0 | |
| ink on tab | 10.5 | 10.7 | |
| ink on paper | 18.9 | 13.5 | the statement and the source |
| ink2 on paper | 9.9 | 8.1 | |
| ink2 on manila | 6.8 | 9.0 | |
| ink2 on tab | 5.5 | 6.4 | |
| red on paper | 5.9 | 5.7 | |
| red on manila | **4.1** | 6.3 | light: stamps of 24 px and up only (3:1 large text) |
| red on redwash | 5.0 | 5.4 | |
| blue on paper | 9.1 | 6.8 | |
| blue on manila | 6.3 | 7.6 | |
| blue on bluewash | 7.7 | 6.1 | |
| onyellow on yellow | 13.2 | 13.2 | sticker, marker |
| ontape on tape | 13.2 | 13.2 | |
| ink on redwash / bluewash | 15.9 / 16.0 | 12.8 / 12.1 | |

Colour is never the only signal: every stamp carries its word.

### Type

Google Fonts: **Archivo** (variable, `wdth 62..125`, `wght 400..900`) and
**Courier Prime** (400, 700, italic 400).

- **Archivo at its narrowest** (`font-stretch: 62%`, weight 800 to 900,
  uppercase, tracked +0.02 to +0.18em) for labels, stamps, the sticker, tabs,
  the wordmark and headings. It is the condensed grotesk of rubber stamps and
  evidence labels.
- **Courier Prime** for every typed field and every quotation: the statement,
  the filing sentence, findings, record fields and hashes. It is the typewriter
  face of evidence forms, drawn for legibility on screen.
- Interface body copy (explanations, the tour) is Courier Prime 400 at 15 px
  minimum. Nothing below 12 px.

| Role | Face | Size / line height |
|---|---|---|
| Cover and thumbnail line | Archivo 900, 62% | 7 to 9% of the width |
| Page heading | Archivo 900, 62%, caps | 30 / 1 (24 phone) |
| Stamp, large | Archivo 900, 62%, caps, +0.06em | 44 to 56 |
| Stamp, small (lists) | Archivo 900, 62%, caps, +0.08em | 15 |
| Sticker number | Archivo 900, 62% | 40 |
| Label (field names, section heads) | Archivo 800, 75%, caps, +0.08em | 12 |
| Statement (the claim) | Courier Prime 700 | 25 / 1.4 (21 phone) |
| Filing sentence | Courier Prime 400 | 16.5 / 1.65 |
| Body, fields, findings | Courier Prime 400 | 15 / 1.55 |
| Fine print (hashes) | Courier Prime 400 | 12.5 / 1.45 |

### Space, shape, motion

- Spacing scale (px): 4, 8, 12, 16, 24, 32, 48. Page gutter 24 desktop, 12 to
  16 phone.
- The folder: `--manila`, square corners, tabs with 8 px top radius.
- The form: `--paper`, square corners, a 3 px `--ink` rule under its heading,
  `--faint` hairlines between fields, and a two-sheet edge below
  (`box-shadow: 0 1px 0 var(--faint), 0 6px 0 -3px var(--faint)`).
- The sticker: 6 px radius, rotated +3deg, `--yellow`, a 1px 2px hard shadow
  at 18% black.
- The stamp: a 4 to 5 px border in the stamp colour, transparent fill, rotated
  -6 to -10deg, with the light ink-spread filter (`feTurbulence` at 0.9 and
  `feDisplacementMap` at scale 2.2). The filter is for stamps only, never text
  that carries evidence.
- The tape: `--tape` with `--ontape` lettering, Archivo 800 at 62%, +0.18em,
  rotated about -1.2deg, clipped by its container.
- Motion: none at rest. A stamp may land once (scale 1.15 to 1, 160 ms) when a
  verdict first renders; Re-verify ticks appear 150 ms apart. All motion off
  under `prefers-reduced-motion`.
- Focus: 3 px `--ink` outline, 2 px offset (on yellow, `--onyellow`).

## 4. Components

- **Wordmark:** the brand name in Archivo 900 at 62%, caps.
- **Folder tabs:** one per ticker, plus "All". The selected tab joins the form
  (same colour as `--paper`).
- **Claim record (the hero):** heading CLAIM RECORD and a one-line source line;
  exhibit sticker top right with the claim id and ticker; fields (Submitted by,
  Stake, Source with the accession link); STATEMENT AS SUBMITTED (typed, wrong
  words ringed); SOURCE, AS FILED (marker on the matched sentence, neighbours
  in `--ink2`); FINDINGS as typed checkboxes (✓ ink, ✗ red); the
  consequence boxes (Stake, Trade, Verdict tx); the stamp in the lower-right
  margin; then the chain of custody.
- **Stamp:** SLASHED + reason, CLEARED + "matches the filing", UNCHECKED +
  "no verdict yet".
- **Evidence tag (list row):** a tag shape with a punched notch, a sticker
  number, the analyst and ticker label, the claim in Courier, a small stamp.
- **Chain of custody:** a ruled table with yellow header: #, From, To, What
  happened, Record. Rows: posted, checked, verdict, desk refusal or trade,
  journal. Slashed and refused rows in red text.
- **Record of reliance (printable):** a full page per paper trade: case
  header, the trade, the claims relied on (each as a small exhibit), the
  refused claims, the chain of custody, the reasoning hash, "How to re-check",
  "What this record does not prove", and a signature-style footer with the
  generation time. Prints on A4 or Letter in black and yellow.
- **Buttons:** primary is `--ink` fill with `--paper` text, Archivo 800 at 75%,
  caps; secondary is a 2 px `--ink` border. No red buttons.
- **The tour:** a typed index card over the folder, one step per card.

## 5. Screens

1. **The feed (`/`):** folder with tape, wordmark, ticker tabs, the claims
   list as evidence tags beside the claim record (desktop) or above it as a
   sheet (phone), the agent's journal, the scoreboard, "For builders".
2. **One claim (`?claim=<id>`):** the claim record alone, for links and the
   video.
3. **The journal (`?journal`):** each paper trade as a case file with its
   chain of custody, Re-verify, Download, and Print the record.
4. **Record of reliance (`?record=<ticker>`):** the printable page.
5. **Check a claim (dialog):** a blank evidence form; the result lands as a
   stamp.

## 6. Submission assets

All generated from HTML in `design/assets/` by `scripts/build_assets.sh`, so
they share the tokens and the name.

- **Cover and thumbnail (1920x1080, also 1280x720):** manila, the tape across
  the top, a typed card with the Qwen statement and "Q3 2026" ringed, the
  sticker EXHIBIT 6, the SLASHED stamp in the margin beside the card (not over
  the words), the line "A citation check for AI-written research" and the
  wordmark.
- **Gallery (1920x1080):** real screens at 1440 px in the light theme, each
  under a tab label: the claim record, the source and findings, the claims
  list, the journal with Re-verify, the record of reliance, the CRE run.
- **Deck:** 1920x1080 slides on manila; typed cards for content; Archivo for
  headings; one sticker per slide at most; at most 25 words of body text;
  body at least 28 px.
- **Video cards:** title card = the cover; lower third = a typed label strip
  (Archivo name, Courier role) on paper with a 3 px ink rule; section cards = a
  folder tab with the section name; "SIMULATION" and "replayed" captions = a
  grey UNCHECKED-style stamp label top right (not red); end card = the cover
  with the URL typed under it.
- **README hero:** the cover image.

## 7. Do and don't

| Do | Don't |
|---|---|
| Ring the wrong words in red inside the statement | Put a stamp or tape over the statement, the filing or the findings |
| Use Cleared, Slashed, Unchecked with a reason | Use TRUE, WRONG, PASS, FAIL or emoji |
| Keep red for Slashed and wrong words | Use red for tape, buttons, links or headings |
| Type the evidence in Courier Prime at full contrast | Fade, texture or tint the evidence |
| Put hashes in fine print, truncated in the middle | Put a hash in a heading, a button or a stamp |
| Number exhibits by their on-chain claim id | Invent exhibit numbers |
| Label replayed and simulated material where it appears | Show a local devnet and call it testnet |
| Check 390 px and 1440 px, light and dark | Ship a screen checked at one width |
| Read the name from `brand.js` / `brand.json` | Hard-code the product name in a new place |
