# Vouch: notes for agents

- The current goal is the BLI Legal Tech Hackathon 2 entry, due 30 Oct 2026.
  The plan is [docs/BLI_PLAN.md](docs/BLI_PLAN.md). Owner-only steps are in
  [docs/bli/OWNER_TODO.md](docs/bli/OWNER_TODO.md).
- Work on the `first-place` branch, and keep `master` fast-forwarded to it.
  The repo is private until Subomi makes it public. Commit under Subomi's name
  with plain messages and no co-author or "Generated with" lines.
- Tests that must stay green: `.venv/bin/python -m pytest -q`, `forge test`,
  and `bun test` in `cre/vouch-verifier` (bun is at `~/.bun/bin`).
- Never print or commit `~/.config/vouch-rh/testnet.key` or `cre/.env`.

## Design

[design/DESIGN.md](design/DESIGN.md) is binding: direction E, Exhibit (a
manila case file, exhibit stickers, evidence tape, rubber stamps, a
chain-of-custody record). It covers every surface a judge sees: the web feed,
the claim page, the record of reliance, the README, the deck, the cover and
the video cards. The rules most likely to be broken:

1. Every claim shows, or links in one click to, the filing sentence it cites,
   with the SEC accession number.
2. One verdict vocabulary: Cleared, Slashed, Unchecked, each with a one-line
   reason. Never TRUE, WRONG, PASS, FAIL or emoji.
3. Stamps and tape frame the evidence and are never laid over it: not over the
   typed statement, the filing sentence or the findings.
4. Red means Slashed or a wrong word, nothing else (the tape is black and
   yellow; buttons and links are ink).
5. The typed statement and the filing sentence stay at full contrast: ink on
   paper or ink on the yellow marker, no opacity, texture or overlay.
6. Hashes are fine print: Courier Prime at most 13 px, truncated in the middle,
   never in a heading, button or stamp.
7. The product name lives in one place (`web/brand.js`, and
   `design/assets/brand.json` for generated assets). Check every screen at
   390 px and 1440 px, light and dark.

Writing: plain prose, no em dashes, no "X, not Y" slogans.
