# Vouch, for lawyers

**Accountability for AI-written research: a record of exactly what an analyst
(human or AI) asserted about a public company, the SEC filing it relied on,
whether the assertion matched that filing, who paid when it did not, and
which trades relied on it.**

This page is for readers who will ask what the record means in law. It
quotes the rules it relies on, says which duties Vouch helps a firm meet,
and says plainly what Vouch does not prove. It is not legal advice.

---

## 1. The gap

US research regulation was written for a person. Regulation AC requires a
*research analyst* to certify that a report's views "accurately reflect the
research analyst's personal views", and defines that analyst as "any
**natural person** who is primarily responsible for the preparation of the
content of a research report" (17 CFR 242.500). FINRA Rule 2241 puts the
duties on the member firm and its "associated persons".

More and more research is drafted by language models. A model can be fluent,
fast and wrong about a number: "$274 million for Q2" from a sentence where
$274 million is the *six-month* figure. Nobody can certify a model's
"personal views". What a firm can do is show, claim by claim, that the facts
it published were checked against the source, and that it acted only on the
ones that held. That is the record Vouch produces.

## 2. The rules, as written

### Regulation AC (17 CFR 242.500 to 242.505)

**What must be certified.** §242.501(a): a broker or dealer or covered
person that publishes or distributes a research report "shall include in that
research report a clear and prominent certification by the research analyst
containing the following:

> (1) A statement attesting that all of the views expressed in the research
> report accurately reflect the research analyst's personal views about any
> and all of the subject securities or issuers; and
>
> (2)(i) A statement attesting that no part of the research analyst's
> compensation was, is, or will be, directly or indirectly, related to the
> specific recommendations or views expressed by the research analyst in the
> research report; or (ii) A statement: (A) Attesting that part or all of the
> research analyst's compensation was, is, or will be, directly or
> indirectly, related to the specific recommendations or views expressed …;
> (B) Identifying the source, amount, and purpose of such compensation; and
> (C) Further disclosing that the compensation could influence the
> recommendations or views expressed in the research report."

**Definitions (§242.500).** *Research report*: "a written communication
(including an electronic communication) that includes an analysis of a
security or an issuer and provides information reasonably sufficient upon
which to base an investment decision." *Research analyst*: "any natural
person who is primarily responsible for the preparation of the content of a
research report." *Public appearance* includes "an interactive electronic
forum".

**The closest the SEC has come to machine-written research.** The adopting
release (33-8193, 2003), on quantitative research: "in cases where there is
no identified analyst because the report is based on the firm's quantitative
or technical model, the firm itself may provide the certifications that the
views expressed in the research report accurately reflect the firm's
quantitative research model". The same release: "A research report contains
an inherent representation that the views expressed in the report are not
knowingly false and do not omit material facts necessary in order to make
statements made not misleading."

**Media exclusion (§242.505)** applies only to a publisher of a "bona fide
newspaper, news magazine or business or financial publication of general and
regular circulation" that is not registered, or required to be registered, as
a broker, dealer or investment adviser.

### FINRA Rule 2241 (Research Analysts and Research Reports, equity)

**Facts (2241(c)(1)).** "A member must establish, maintain and enforce
written policies and procedures reasonably designed to ensure that: (A)
purported facts in its research reports are based on reliable information;
and (B) any recommendation, rating or price target has a reasonable basis and
is accompanied by a clear explanation of any valuation method used and a fair
presentation of the risks". Regulatory Notice 15-30 describes (c)(1)(A) as
new when the rule was adopted.

**Objective research (2241(b)(2)).** Policies "reasonably designed to promote
objective and reliable research that reflects the truly held opinions of
research analysts".

**Third-party research (2241(h)(2) and (h)(3)).** "A member may not distribute
third-party research if it knows or has reason to know such research is not
objective or reliable", and must have policies so that third-party research
"contains no untrue statement of material fact and is otherwise not false or
misleading."

**Scope.** 2241 covers equity research (debt is Rule 2242) and excludes, among
others, communications "distributed to fewer than 15 persons" and "internal
communications that are not given to current or prospective customers"
(2241(a)(11)).

### FINRA on generative AI and AI agents

- **Regulatory Notice 24-09 (June 2024):** FINRA's rules "are intended to be
  technology neutral" and "continue to apply when member firms use Gen AI";
  the content standards of Rule 2210 "apply whether member firms'
  communications are generated by a human or technology tool". The notice
  "does not create new legal or regulatory requirements".
- **Advertising FAQ D.8 (May 2024):** "Firms are responsible for their
  communications, regardless of whether they are generated by a human or AI
  technology."
- **2026 Annual Regulatory Oversight Report (GenAI):** among the risks of AI
  agents, "Auditability and Transparency: Complicated, multi-step agent
  reasoning tasks can make outcomes difficult to trace or explain"; firms
  should consider "how to track agent actions and decisions; or how to
  establish guardrails or control mechanisms to limit or restrict agent
  behaviors, actions or decisions", and "storing prompt and output logs for
  accountability".

### Anti-fraud, for everyone

Rule 10b-5(b) and Securities Act §17(a)(2) reach "any untrue statement of a
material fact" in connection with the purchase or sale of a security, by any
person, registered or not.

## 3. Where Vouch fits

| Duty | What it asks | What Vouch provides |
|---|---|---|
| FINRA 2241(c)(1)(A) | Procedures reasonably designed so that *purported facts* in research are based on reliable information | A check of every numeric fact against the issuer's own SEC filing: the quote must be a whole sentence of the filing, every figure exact, the period, quarter, date and direction as filed. Run the same way every time, with the result and the filing's hash on record. |
| FINRA 2241(h)(2)-(3) | Do not distribute third-party research you have reason to know is unreliable; no untrue statements of material fact | A per-claim public record of which third-party (including AI) claims failed, with the reason. A firm can refuse to republish anything not cleared. |
| Reg AC §501(a)(2) | Disclose compensation related to the views | The analyst's stake is public and on-chain: amount, claim, outcome. If a stake is compensation "related to the specific … views", the record is the disclosure's source, amount and purpose. (See open questions.) |
| Reg AC, quantitative model passage | Where a model writes the report, the firm certifies the views reflect its model | The firm can certify that the model's factual statements were checked, and show the check for each one. |
| FINRA 2026 report on AI agents | Traceable agent decisions, guardrails on agent actions, logs for accountability | `AgentDesk` is the guardrail (an agent cannot cite research that failed the check: the trade reverts); the journal is the trace (each trade's cited claims, their verdicts and the agent's reasoning, hashed on-chain when the trade is made). |

## 4. In plain language: what is attested, by whom

| Statement | Made by | Recorded where | What would show it false |
|---|---|---|---|
| "I say *these exact words* about this company, citing filing *X*, and I put *N* USDG behind them." | The analyst's wallet (a person or an AI agent's key) | `Posted` event: the words, their keccak256, the stake, the time | Nothing can: the words cannot be edited after posting |
| "Our nodes fetched filing *X* from SEC EDGAR, its bytes hash to *E*, and the claim's quote, figures, period and direction do (or do not) match it." | In production: a Chainlink decentralised oracle network running the published workflow. In the CLI simulation (all that can exist by the deadline): a single local node runs the same workflow, and the transaction is sent by the operator through Chainlink's unauthenticated mock forwarder, so the record shows what the workflow computed but not that anyone independent computed it. In the fallback round shown today: the workflow's code in Chainlink's SDK test runtime, on a local devnet. In the v1 testnet round of 24 Sep: one verifier key | `Checked` event: verdict, reason, *E*, the workflow id (zero when no DON set one) | Download filing *X*, drop the one script tag SEC's CDN adds, hash it, re-run the open-source check: a different answer is proof |
| "This analyst loses the stake" / "keeps it" | The contract, automatically | The same transaction as the verdict | It cannot diverge from the verdict |
| "At time *T* this agent opened a paper position citing claims *A, B*, each cleared, for these reasons." | The trading agent's wallet; the desk contract enforces that every cited claim was cleared | `Opened` event: the citations, the verdict on each, the reasoning hash | Re-hash the published reasoning; re-run the agent's rules; any difference shows |

## 5. Who is liable

Vouch changes who **pays** for a wrong number. It does not move anyone's
legal duties.

- **The firm that publishes or distributes research** keeps its Reg AC and
  Rule 2241 obligations, whoever or whatever drafted the report (Notice 24-09,
  FAQ D.8). Vouch is a control it can use and show to an examiner, not a
  substitute for supervision.
- **The analyst** (or whoever operates an AI analyst) bears the economic
  consequence: the stake. That is a contractual consequence the analyst
  accepts by bonding, not a finding of fault, and it does not displace anyone's
  claims under the securities laws.
- **Anyone** who makes an untrue statement of a material fact in connection
  with a securities transaction remains exposed under Rule 10b-5 and §17(a). A
  cleared claim is not a safe harbour: a true figure can still mislead by what
  it leaves out.
- **The operator of a trading agent** is responsible for its trades. The
  journal is their evidence of what the agent relied on and why.
- **Vouch and the Chainlink network** attest one narrow thing: that a quoted
  figure matches the issuer's filing. They give no opinion on any security.

## 6. What the on-chain record proves, and what it does not

**It proves**

- the exact words of each claim, who staked on them and when (they cannot be
  edited after posting);
- which filing the verdict was checked against, byte for byte (the keccak256
  of the document as SEC serves it, less the one script tag SEC's CDN adds),
  and, on a DON, which workflow produced the verdict;
- that the verdict and the money moved in the same transaction;
- that a trade cited only claims that were cleared at the time, and that its
  stated reasons were fixed when it was made.

**It does not prove**

- **that a view was honestly held.** Reg AC's certification is about belief;
  a check of figures cannot reach belief. Vouch checks facts, not opinions.
- **that a recommendation had a reasonable basis** (2241(c)(1)(B)): Vouch
  does not check ratings, price targets or valuation.
- **that the filing is true.** Vouch checks claims against what the issuer
  filed; an error in the filing passes through.
- **that a claim is complete or material.** A correct figure, selectively
  quoted, can still mislead.
- **who is behind a wallet.** Identity, registration and supervision are the
  firm's records, not the chain's.
- **compliance with SEC Rule 17a-4.** Since January 2023, 17a-4(f) allows an
  audit-trail alternative to WORM storage ("a complete time-stamped audit
  trail … [that] will permit re-creation of the original record if it is
  modified or deleted"). An append-only public ledger has those properties
  for what it holds, but a broker-dealer's recordkeeping system also needs
  third-party undertakings, production to regulators and retention controls
  (17a-4(f), (i)). Vouch could be one component of that system, not the system.

**Limits of the check, stated by the check.** It cannot tell a borrowing
limit from a balance, or an inflow from an outflow described only in words.
Those are what the challenge window and human challengers are for.

## 7. Who uses it

- **A compliance officer** at a broker-dealer distributing AI-drafted or
  third-party research: publish only cleared claims; keep the check's record
  for each one as evidence of 2241(c)(1)(A) procedures.
- **A research publisher or newsletter** using AI drafting: a per-claim
  public record that the numbers were checked, and a stake that shows it.
- **The operator of an AI trading agent:** the desk's guardrail and the
  journal's trace, the two things FINRA's 2026 report asks about agents.
- **An examiner, auditor or litigator:** an independent, re-runnable record
  of what was said, what the source said, and what was done about it. Each
  journal entry downloads as a single audit record (Markdown): the exact words,
  hashes, filing, verdicts, refusals and reasoning, with the steps to check
  each line and this page's list of what it does not prove.

## 8. Open questions we flag rather than answer

- Whether an analyst's stake is "compensation … related to the specific
  recommendations or views" under Reg AC §501(a)(2). If so, §501(a)(2)(ii)
  disclosure applies, and the on-chain record supplies it.
- Whether a stake-and-slash market on research is itself a security,
  swap or wager in a given jurisdiction. The deployment here is a testnet
  with test tokens.
- Whether operating the verifier or the feed could make a party an
  investment adviser or a publisher of research; §242.505's media exclusion
  covers only unregistered publishers "of general and regular circulation".
- Tokenised stocks: whether a token is an "equity security" for Rule 2241
  purposes. Vouch checks claims about the issuer's filing either way.

## Sources

- Regulation AC, 17 CFR 242.500 to 242.505 (eCFR): https://www.ecfr.gov/current/title-17/chapter-II/part-242/subpart-AC
- SEC Release 33-8193 / 34-47384 (2003), adopting Regulation AC: https://www.sec.gov/files/rules/final/33-8193.htm
- FINRA Rule 2241: https://www.finra.org/rules-guidance/rulebooks/finra-rules/2241
- FINRA Regulatory Notice 15-30: https://www.finra.org/rules-guidance/notices/15-30
- FINRA Regulatory Notice 24-09: https://www.finra.org/rules-guidance/notices/24-09
- FINRA Advertising Regulation FAQ D.8: https://www.finra.org/rules-guidance/guidance/faqs/advertising-regulation
- FINRA 2026 Annual Regulatory Oversight Report, GenAI: https://www.finra.org/rules-guidance/guidance/reports/2026-finra-annual-regulatory-oversight-report/gen-ai
- FINRA Rule 2210: https://www.finra.org/rules-guidance/rulebooks/finra-rules/2210
- SEC Rule 17a-4 amendments, Release 34-96034 (87 FR, 3 Nov 2022): https://www.federalregister.gov/documents/2022/11/03/2022-22670/
- 17 CFR 240.10b-5; Securities Act §17(a), 15 U.S.C. 77q(a)

Quotations were taken from these primary sources on 13 October 2026.
