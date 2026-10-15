# Vouch design spec

Binding for every surface a judge sees: the web feed (`web/`), the audit
record, the README hero, the cover and gallery images, the deck, and the
video's cards. Three directions are compared in
[`directions.html`](directions.html). **The tokens below are direction A, The
Record (recommended).** If Subomi picks B or C, replace the Tokens section with
that direction's values from `directions.html` and keep everything else.

Audience: lawyers, compliance officers and a few Web3 and sponsor judges (BLI
Legal Tech Hackathon 2; last year's panel included a law-firm partner and
corporate counsel). They decide from a 2:30 video and a few seconds on each
page. A 2025 judge wrote that entries' "legal applicability fell short". The
design's job is to make the evidence legible before anything else.

## 1. Audit of today's design (14 Oct build)

Screens checked in headless Chrome at 1440 px and 390 px, plus the deck PDF
and `docs/cover.png`.

What reads as generic or wrong for this panel, worst first:

1. **A crypto trading terminal.** Near-black `#050505`, acid lime `#ccff00`
   on the primary button, a scrolling ticker tape of "WRONG" and "TRUE" in
   caps, and price-board tiles per stock. To a lawyer it reads as a meme-coin
   dashboard, which is the exact impression the audit warned about ("a crypto
   trading toy with legal garnish").
2. **Mono caps everywhere, in low-contrast grey.** Section labels, metadata
   and the inspector's headings are 11 to 12 px letter-spaced JetBrains Mono
   in mid-grey. Deck body text is unreadable at gallery size. Inter Tight with
   JetBrains Mono is the default pairing of this year's AI-made dashboards.
3. **A stale, inconsistent submission surface.** `docs/cover.png` still says
   "Arbitrum Open House Singapore". The verdict has four vocabularies on one
   screen (TRUE/WRONG in the tape, Cleared/Slashed in tabs, "true 18 wrong 32"
   in the KPIs, "matches the filing" in rows).
4. **Phone breaks.** At 390 px the tour's hero sentence is clipped
   ("billio") and the progress bar runs off the right edge.
5. Everything is a rounded dark card with a 1 px border; the inspector, the
   money boxes and the trading box all have the same weight, so the verdict
   does not stand out from its metadata.

What already works and stays: the inspector's structure (claim, quoted
sentence, the filing's sentence in context, money, what the agent did),
"Right number, wrong quarter. Slashed." as a headline, Re-verify, the audit
record download, and the honest "what it does not prove" copy.

## 2. Principles (testable)

1. **The source is one click from every claim, and visible on the hero.** Any
   screen that shows a claim also shows, or links in one click to, the filing
   sentence it cites, with the accession number. Test: pick any claim on any
   screen; the filing sentence is reachable in one click.
2. **Quoted words look quoted.** The claim's words and the filing's words are
   set in the serif, verbatim, never paraphrased, never truncated mid-number.
   Interface text is never set in the serif. Test: every serif string on a
   screen is a verbatim quotation.
3. **One verdict vocabulary, one signal.** "Cleared" (green flag) and
   "Slashed" (red flag), plus "Unchecked" (amber flag) for a claim with no
   verdict. Each signal carries a one-line reason in plain English. No TRUE,
   WRONG, PASS or FAIL anywhere a judge sees. Test: grep the page text.
4. **Provenance is footnoted, not shouted.** Hashes, transaction ids and
   addresses live in footnotes, the margin record and the audit record, in
   mono at 12.5 px, truncated in the middle (`0xbed0273d…12892`) and copyable
   in full. They never appear in a headline or a button. Test: no hex string
   larger than 13 px.
5. **Say what ran and what is trusted, once.** Caveats sit in one "What ran"
   box per surface, not in every sentence. Labels like "replayed" and
   "simulation" are shown where the thing is shown. Test: one caveat box per
   page; each replayed claim carries the label.
6. **Readable by a 60-year-old partner on a laptop.** Body text at least
   15 px, quoted claims at least 19 px, every text colour at least 4.5:1
   against its background, nothing below 12 px. Test: the contrast table in
   section 4 and a computed-style sweep.
7. **Nothing moves unless it reports progress.** No ticker tape, no ambient
   animation. Motion is allowed only for Re-verify ticks, the tour's step
   change and focus. Test: with no interaction, two screenshots a second apart
   are identical.

## 3. Reference board

| Product | Take | Avoid |
|---|---|---|
| Westlaw KeyCite flags | The red, yellow and green flag as "is this authority still good?": our Slashed, Unchecked, Cleared | Thomson Reuters orange and their dense chrome; never copy their icon |
| Lexis Shepard's signals | Signal plus a one-line reason, always together | The many-symbol signal zoo |
| Harvey | Answers with inline citations that open the source passage | Dark luxury marketing gradients |
| CourtListener (Free Law Project) | Plain public-record typography, citations as ordinary links | Dated page chrome |
| SEC EDGAR filing index | Accession number, form type, period and filing date as first-class metadata | 1990s table layout |
| FINRA rulebook pages | Numbered paragraphs and pinpoint citations (2241(c)(1)(A)) | Weak heading hierarchy |
| Litera Compare and Draftable | The redline convention for a mismatch: red wavy or strike on the claim's wrong words | A full split pane as the hero (kept as direction B) |
| Stripe receipts and docs | Key and value records, restraint, generous line height | Purple gradients |
| GOV.UK Design System | Plain-English content rules, large body text, strong focus states | Government branding |
| Etherscan transaction page | The fields people verify (tx, block, events), as a model for our margin record | Ads, density, crypto chrome |
| Financial Times | Serif quotation inside a sans interface | The salmon background (cream slop) |

## 4. Tokens (direction A, The Record)

### Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#FFFFFF` | `#111418` | page |
| `--surf` | `#F5F6F8` | `#181C22` | panels, table header, code |
| `--ink` | `#14171C` | `#E8EAED` | text, primary button |
| `--ink2` | `#4A5260` | `#A6ADB8` | secondary text, labels |
| `--rule` | `#D5D9E0` | `#2C333D` | hairlines (never for text) |
| `--cite` | `#1D4E89` | `#8DB4E8` | links, citations |
| `--red` / `--redbg` | `#B42318` / `#FDECEA` | `#F2827A` / `#3A1D1B` | Slashed, the wrong words |
| `--green` / `--greenbg` | `#1E6B3A` / `#E8F3EC` | `#6CC58F` / `#16301F` | Cleared |
| `--amber` / `--amberbg` | `#7A4F00` / `#FFF4D6` | `#E6B656` / `#3A2E10` | Unchecked, replayed, simulation labels |
| `--mark` | `#FFF1A8` | `#4A4214` | highlighter on the filing's matched sentence |

Contrast, computed with the WCAG 2 formula (text on background):

| Pair | Light | Dark |
|---|---|---|
| ink on bg / surf | 18.0 / 16.6 | 15.3 / 14.2 |
| ink2 on bg / surf | 7.9 / 7.3 | 8.2 / 7.6 |
| cite on bg | 8.4 | 8.6 |
| red on bg / on redbg | 6.6 / 5.7 | 7.3 / 6.0 |
| green on bg / on greenbg | 6.5 / 5.7 | 8.8 / 6.8 |
| amber on bg / on amberbg | 7.1 / 6.5 | 9.8 / 7.1 |
| ink on mark | 15.7 | 8.4 |

All pass AA for body text; ink and ink2 pass AAA. Colour is never the only
signal: every flag has a word next to it.

### Type

Google Fonts: Source Serif 4 (opsz 8..60, 400/600/700), IBM Plex Sans
(400/500/600), IBM Plex Mono (400/500).

- Source Serif 4 is a screen-tuned text serif with optical sizes, so a quoted
  claim reads like a quotation in a brief at 19 px and like a title at 56 px.
- IBM Plex Sans is neutral, has true tabular figures, and is not this year's
  default AI-dashboard face.
- IBM Plex Mono matches Plex Sans's metrics for hashes and accession numbers.

| Role | Font | Size / line height | Weight |
|---|---|---|---|
| Display (cover, deck titles) | Serif | 56 / 1.1 (thumbnail 5.6% of width) | 600 |
| Page title | Serif | 32 / 1.2 | 600 |
| Claim quotation | Serif | 21 / 1.5 (19 on phone) | 400 |
| Filing quotation | Serif | 17.5 / 1.65 | 400 |
| Body | Plex Sans | 15 / 1.6 | 400 |
| Section label | Plex Sans | 12.5, caps, 0.06em tracking | 600 |
| Small, metadata | Plex Sans | 13 / 1.5 | 400 |
| Identifier | Plex Mono | 12.5 / 1.45 | 400 |

Figures in tables use `font-variant-numeric: tabular-nums`.

### Space, radius, motion

- Spacing scale (px): 4, 8, 12, 16, 24, 32, 40, 64. Page gutter 40 desktop,
  16 phone. Document column at most 680 px; margin record 250 px.
- Radius: 3 px on buttons, flags and signal boxes; 6 px on framed screens;
  0 on tables. No pills, no 12 px+ rounded cards.
- Borders: 1 px `--rule` hairlines; the claim quotation has a 2 px `--ink`
  left rule, the filing quotation a 2 px `--rule` left rule.
- Motion: 120 ms ease-out for hover and focus; 200 ms for a tour step; each
  Re-verify tick appears 150 ms after the previous one. Everything off under
  `prefers-reduced-motion`.
- Focus: 2 px `--cite` outline, 2 px offset, on every interactive element.

## 5. Components and screens

Components: wordmark (serif "Vouch" with a small flag), top nav, verdict
signal box, flag (inline), claim quotation with wrong-words underline, filing
quotation with highlighter and context, numbered findings, consequence list,
footnote, margin record, primary and secondary buttons, claims table, filter
tabs, search, journal entry (Read, Refused, Relied on, Decided, To re-check),
Re-verify tick list, "What ran" box, replayed and simulation labels (amber).

Screens, in priority order:

1. **Claim view (the hero).** As in directions.html: running header with the
   filing, verdict signal, claim, cited source, findings, consequence,
   footnote, margin record. It is the first thing the page shows.
2. **Claims list.** Analyst, claim (serif), signal with reason.
3. **Agent journal.** One entry per paper trade, Re-verify, Download.
4. **Record of reliance.** The audit record as a printable page (print CSS),
   in addition to the Markdown download.
5. **Tour.** Five steps over the same claim; on phone, full width, no
   clipping.
6. **Check a claim** dialog.
7. **For builders** (API, MCP, `isCleared`), at the foot.
8. **KOL / news-checker mode** (`?feed=feed-kol.json`): the same claim view,
   with the post shown as the claim.

Remove: the ticker tape and the price-board tiles. Keep per-stock counts as a
plain line in the claims list header.

## 6. Submission assets

- **Cover and thumbnail (1920x1080):** white page, serif display line "A
  citation check for AI-written research." with the highlighter on three
  words, the red flag line "Slashed: the AI said Q3. The filing says June 30."
  in Plex Sans, wordmark bottom right, the event and Chainlink CRE in a small
  caps line top left. No gradients, no glow, no chain logos except Chainlink's
  where its brand rules allow.
- **Gallery images (1920x1080, 4 to 6):** real screens at 1440 px, light
  theme, cropped to one idea each (the claim view, the cited source, the
  journal, the record of reliance, the CRE run). A one-line serif caption on a
  white band above each.
- **Deck:** same tokens, light theme, at most 25 words of body per slide,
  body text at least 24 px at 1920 wide.
- **Video cards:** title card and end card are the cover layout. Lower
  thirds: white band, 2 px ink rule on the left, serif name, sans role. Every
  "SIMULATION" or "replayed" caption is an amber label, top right, for as long
  as that footage is on screen.
- **README hero:** the cover image, then the one-liner. No badges row above
  the fold.
- **Logo:** the flag mark alone, ink on white; red only when it means Slashed.

## 7. Do and don't

| Do | Don't |
|---|---|
| Quote the filing verbatim, with its accession number | Paraphrase a filing or a claim |
| Use Cleared, Slashed, Unchecked, each with a reason | Use TRUE, WRONG, PASS, FAIL, or emoji |
| Put hashes in footnotes and the margin | Put a hash in a headline, a button or the thumbnail |
| Keep one "What ran" box per surface | Hedge in every sentence |
| White page, black ink, one red, one green, one highlighter | Lime, neon, purple or blue gradients, cream and terracotta |
| Serif for quotations only | Serif for buttons, labels or numbers in tables |
| Label replayed and simulated material where it appears | Show a local devnet and call it testnet |
| Test at 390 px and 1440 px, light and dark | Ship a screen only checked at one width |
