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

[design/DESIGN.md](design/DESIGN.md) is binding for every surface a judge
sees: the web feed, the audit record, the README, the deck, the cover and the
video cards. The rules most likely to be broken:

1. Every claim shows, or links in one click to, the filing sentence it cites,
   with the accession number.
2. Serif type is for verbatim quotations only (the claim, the filing). Never
   for buttons, labels or table numbers.
3. One verdict vocabulary: Cleared, Slashed, Unchecked, each with a one-line
   reason. Never TRUE, WRONG, PASS, FAIL or emoji.
4. Hashes and transaction ids go in footnotes and the margin record, in mono,
   at most 13 px, truncated in the middle. Never in a headline or a button.
5. No lime, neon, gradients or ticker tape. Nothing moves unless it reports
   progress. Check every screen at 390 px and 1440 px, light and dark.

Writing: plain prose, no em dashes, no "X, not Y" slogans.
