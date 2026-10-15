# Robinhood Chain testnet round

The first half of the CRE round: the market is deployed and every claim is posted
on Robinhood Chain testnet (chain id 46630). Nothing is settled yet: the verdicts come
from the Chainlink CRE workflow in the CRE CLI simulation, which needs `cre login`.
The claims wait, pending, for the 7-day window (until 22 Oct 2026, 16:32 UTC). After
the login, one command settles them and rewrites this page:

```
bash scripts/after_login.sh
```

Evidence folder: `cre/runs/20261015T163010Z-posted/`. Workflow WASM: `077ae634fa6419380c91bba594a9205db996434c427a92005492e9b829fb73eb`. The AI analyst's claims are
Qwen 2.5 7B's words from the 24 Sep round, replayed word for word (labelled replayed).

## Contracts

| Contract | Address |
|---|---|
| BondedClaims (verdicts only from the forwarder) | [0x3234bd274FF76aB2eB3487eC91cD14cbAc3E1a33](https://explorer.testnet.chain.robinhood.com/address/0x3234bd274FF76aB2eB3487eC91cD14cbAc3E1a33) |
| AgentDesk | [0x59Cd19438CDAe1eDBa5F3045aF3a01B1D33b4039](https://explorer.testnet.chain.robinhood.com/address/0x59Cd19438CDAe1eDBa5F3045aF3a01B1D33b4039) |
| Test USDG (tUSDG) | [0xD1c5756B52914bA790E613198D69458C972FA90F](https://explorer.testnet.chain.robinhood.com/address/0xD1c5756B52914bA790E613198D69458C972FA90F) |
| Chainlink MockKeystoneForwarder (simulation) | [0x0b93082D9b3C7C97fAcd250082899BAcf3af3885](https://explorer.testnet.chain.robinhood.com/address/0x0b93082D9b3C7C97fAcd250082899BAcf3af3885) |

Deployer and funder: `0x950d00BA837cD285e6d8a0F3f02d69434a775808` (test wallet).

## The claims

All 50 posting transactions succeeded (receipts checked 15 Oct). "Expected" is what the
same check gives locally before any gas; the on-chain verdict will be the workflow's.

| Claim | Stock | Analyst | Figure | Expected | Posted in |
|---|---|---|---|---|---|
| 0 | TSLA | Diligent | $8.28 billion | cleared | [0xf8463c09…5412f3](https://explorer.testnet.chain.robinhood.com/tx/0xf8463c0905da50316e5c7d393333d2baba64b7718284f44d3dee68ffdb5412f3) |
| 1 | TSLA | Qwen 2.5 7B (AI, replayed) | $8.63 billion | cleared | [0x951f5f8a…6cb20a](https://explorer.testnet.chain.robinhood.com/tx/0x951f5f8a5717d38047dac9bc256265347f29e8b22a90d39f4de74a9dfd6cb20a) |
| 2 | TSLA | Misreader | $4.05 billion | slashed | [0x53ece196…61e0b2](https://explorer.testnet.chain.robinhood.com/tx/0x53ece1962745f6b97996da10372a695fbb5ddafa32f8bc4fa9824a9a8e61e0b2) |
| 3 | TSLA | Embellisher | $8.29 billion | slashed | [0xa18c6285…bad115](https://explorer.testnet.chain.robinhood.com/tx/0xa18c6285825b47f87e4bfa3e36fb5184b1455631d37b51cc5e56805573bad115) |
| 4 | TSLA | Fabricator | $0.28 billion | slashed | [0x942d3faa…b5598e](https://explorer.testnet.chain.robinhood.com/tx/0x942d3faaf5bd52c036d463f590140c256863ed80589d9e978368e4de3eb5598e) |
| 5 | TSLA | Diligent | $1.37 billion | cleared | [0xd30a602a…9dcc48](https://explorer.testnet.chain.robinhood.com/tx/0xd30a602afb95f0903cfb7c24b2263749cdc60436768d9e9d96ef04f8a79dcc48) |
| 6 | TSLA | Qwen 2.5 7B (AI, replayed) | $1.37 billion | slashed | [0x40969fdd…3df8e8](https://explorer.testnet.chain.robinhood.com/tx/0x40969fdd3e7b8d72fcfd17ea241b484e9792027bd40d68ba501d07b17c3df8e8) |
| 7 | TSLA | Misreader | $4.05 billion | slashed | [0x9ff08419…482b4e](https://explorer.testnet.chain.robinhood.com/tx/0x9ff084199ebdc7b70c6690ae39a34bc3154a87ec2b2244ad835322ef2f482b4e) |
| 8 | TSLA | Embellisher | $1.47 billion | slashed | [0xf1e6d1b0…a239b2](https://explorer.testnet.chain.robinhood.com/tx/0xf1e6d1b02cc5f17f84c8a44de8d54f4c0995a6aef15ab042214e046b27a239b2) |
| 9 | TSLA | Fabricator | $4.37 billion | slashed | [0xecfe083a…110653](https://explorer.testnet.chain.robinhood.com/tx/0xecfe083a71d740b60e18536e6bcfb95ae50a4b903c6a6a55ede7a03317110653) |
| 10 | AMZN | Diligent | $28.7 billion | cleared | [0x8af69126…db8af8](https://explorer.testnet.chain.robinhood.com/tx/0x8af6912691154f137bcc88ed5f3b56d34c23dd222847e17f883578c9bddb8af8) |
| 11 | AMZN | Qwen 2.5 7B (AI, replayed) | $28.7 billion | cleared | [0x0d0be422…8939b7](https://explorer.testnet.chain.robinhood.com/tx/0x0d0be4224c7cd5de17f5afa0394eda4d7ddf6c2587f5a6f21aa47d5c378939b7) |
| 12 | AMZN | Misreader | $640 million | slashed | [0xf73a1b31…4bd983](https://explorer.testnet.chain.robinhood.com/tx/0xf73a1b31af9d47ed6ece7693abc6c3d4da7fb5e9a4c5b09aa29c299b114bd983) |
| 13 | AMZN | Embellisher | $38.7 billion | slashed | [0xbdcd62ed…32d6b4](https://explorer.testnet.chain.robinhood.com/tx/0xbdcd62ed760a097cefa652a76378b1fd36bafb8cb037ec95b90f46bbb932d6b4) |
| 14 | AMZN | Fabricator | $38.7 billion | slashed | [0xd1e72482…d4543a](https://explorer.testnet.chain.robinhood.com/tx/0xd1e72482884c740805a200fb927c0afe959ca1a3052e53522b4aab8fead4543a) |
| 15 | AMZN | Diligent | $21.3 billion | cleared | [0xb3029906…b5f70b](https://explorer.testnet.chain.robinhood.com/tx/0xb30299066ff19ea334f8df516fd04d430921f89c6e89f38a4eb2992a05b5f70b) |
| 16 | AMZN | Qwen 2.5 7B (AI, replayed) | $21.3 billion | cleared | [0x00eb3193…4c1201](https://explorer.testnet.chain.robinhood.com/tx/0x00eb31932037a0bc0d691fecdb17e4e510fa271241985bbb981694130d4c1201) |
| 17 | AMZN | Misreader | $640 million | slashed | [0x7d2aaeec…bdbe0a](https://explorer.testnet.chain.robinhood.com/tx/0x7d2aaeec8cac9236f0387fa257710e8445582e8c59313d31d56d425b9bbdbe0a) |
| 18 | AMZN | Embellisher | $28.3 billion | slashed | [0x7f629c37…17c4ad](https://explorer.testnet.chain.robinhood.com/tx/0x7f629c37fdcb20794ae3a4fd928a1dbb372104d7a48a28d30f98addae917c4ad) |
| 19 | AMZN | Fabricator | $21.0 billion | slashed | [0x505b1256…cd3253](https://explorer.testnet.chain.robinhood.com/tx/0x505b125647dc1aa5496d040af64b57b9a017e94d0206163cc7810fd387cd3253) |
| 20 | PLTR | Diligent | $50 million | cleared | [0x938620a7…89c2f2](https://explorer.testnet.chain.robinhood.com/tx/0x938620a7da2e7d1bfb409681e1e7e6a5796ceff135cd5b3b6baefca03289c2f2) |
| 21 | PLTR | Qwen 2.5 7B (AI, replayed) | $5.6 billion | cleared | [0xe4017282…9415ce](https://explorer.testnet.chain.robinhood.com/tx/0xe4017282c18c17b7f6bb4647e09b6e5c2a220f2ac6b727c049432e5c289415ce) |
| 22 | PLTR | Misreader | $1.5 billion | slashed | [0x976d302f…787947](https://explorer.testnet.chain.robinhood.com/tx/0x976d302f02d7263ad1f151870cd5e2268c96f6dc1d688239b94d31c592787947) |
| 23 | PLTR | Embellisher | $70 million | slashed | [0x1e88521a…28e411](https://explorer.testnet.chain.robinhood.com/tx/0x1e88521a11d1539cde1add205e45c3ce4518685c87fbb8c97ce76f025a28e411) |
| 24 | PLTR | Fabricator | $51 million | slashed | [0xbc053530…f87c23](https://explorer.testnet.chain.robinhood.com/tx/0xbc053530fd3e3412f991858afc47e761f54bf0b91b89388b6d9bb7f36af87c23) |
| 25 | PLTR | Diligent | $916 million | cleared | [0x83d1f5bc…36b789](https://explorer.testnet.chain.robinhood.com/tx/0x83d1f5bcf82978185577b41d2dbffe7f167e639990029e22dbdb1a443b36b789) |
| 26 | PLTR | Qwen 2.5 7B (AI, replayed) | $361 million | cleared | [0x23ab5dbd…d88a1a](https://explorer.testnet.chain.robinhood.com/tx/0x23ab5dbdda0c67fff25cf160894fb9a665df05f26c8dce53f8131c56c2d88a1a) |
| 27 | PLTR | Misreader | $1.5 billion | slashed | [0x01ed95f4…0691fa](https://explorer.testnet.chain.robinhood.com/tx/0x01ed95f4e565e4c3312a6f715c99370703c54719b101bc256fb03282010691fa) |
| 28 | PLTR | Embellisher | $917 million | slashed | [0x60741d2e…ee5ad8](https://explorer.testnet.chain.robinhood.com/tx/0x60741d2e3991d172432fb310a5f414311380397fdf388cf13e30e4dac5ee5ad8) |
| 29 | PLTR | Fabricator | $913 million | slashed | [0xca56069f…e06162](https://explorer.testnet.chain.robinhood.com/tx/0xca56069f4ea18eeb9e2e76e784979763b9de534e920ec4e245f64a7110e06162) |
| 30 | NFLX | Diligent | $5.1 billion | cleared | [0x8c6c7c14…c3600c](https://explorer.testnet.chain.robinhood.com/tx/0x8c6c7c14af4b3dba33bcddef67dd5de82ee7c6ecd5ffebd2246153ce9ac3600c) |
| 31 | NFLX | Qwen 2.5 7B (AI, replayed) | $5.1 billion | cleared | [0x2d72e4b7…dffc18](https://explorer.testnet.chain.robinhood.com/tx/0x2d72e4b7aa102ac0d4ab9e573a577dd9ace464382bf53cdf3ea39ca708dffc18) |
| 32 | NFLX | Misreader | $127 million | slashed | [0x1d72a71a…abba96](https://explorer.testnet.chain.robinhood.com/tx/0x1d72a71a5f271d7af4ada903280ef47e321a9300d3763c6eaf211487f6abba96) |
| 33 | NFLX | Embellisher | $7.1 billion | slashed | [0xc6491f5d…fc0e7d](https://explorer.testnet.chain.robinhood.com/tx/0xc6491f5df2de86dcfe94b8660ac4ddc2481f32ed9e81e3418eadd3eac3fc0e7d) |
| 34 | NFLX | Fabricator | $5.2 billion | slashed | [0xb622fe59…908e57](https://explorer.testnet.chain.robinhood.com/tx/0xb622fe590320ae6692a9a334d4ab0cebdfe22d087bde51808eced9f241908e57) |
| 35 | NFLX | Diligent | $9 million | cleared | [0xa606efaa…f542f8](https://explorer.testnet.chain.robinhood.com/tx/0xa606efaa71bcefdf8d495650f3fbcb5087bfb693adeede0542b63e9013f542f8) |
| 36 | NFLX | Qwen 2.5 7B (AI, replayed) | $17 million | cleared | [0xd4875d1a…07e44f](https://explorer.testnet.chain.robinhood.com/tx/0xd4875d1a0e6d920dde5486377ac95fb892da53531c927c4b715043541d07e44f) |
| 37 | NFLX | Misreader | $127 million | slashed | [0x46632f3d…c2b80d](https://explorer.testnet.chain.robinhood.com/tx/0x46632f3d87940ef814b49df2d03eaf9611494c8fb6e59ca1ca79672c87c2b80d) |
| 38 | NFLX | Embellisher | $0 million | slashed | [0x8cad53f3…afbb5c](https://explorer.testnet.chain.robinhood.com/tx/0x8cad53f3405d151a6699833787dc0ca76e690e2dbc8ab6e9adeca3f232afbb5c) |
| 39 | NFLX | Fabricator | $2 million | slashed | [0xc24d3ed6…57ea37](https://explorer.testnet.chain.robinhood.com/tx/0xc24d3ed6b47a77e5d87f3a3d6a53220eb4ee3adda1d4fc31b9f774bdaa57ea37) |
| 40 | AMD | Diligent | $544 million | cleared | [0xfbffc9ce…cb2b5e](https://explorer.testnet.chain.robinhood.com/tx/0xfbffc9cef89c422e2543bfa9bd9b0a52c03c406de323dceb1f7a1d0e68cb2b5e) |
| 41 | AMD | Qwen 2.5 7B (AI, replayed) | $544 million | slashed | [0xe6661153…28c086](https://explorer.testnet.chain.robinhood.com/tx/0xe66611530554f9e6d60ec8ceaf976798119af2d9694eca1e1e83c9357b28c086) |
| 42 | AMD | Misreader | $222 million | slashed | [0xed5e809f…b6fc03](https://explorer.testnet.chain.robinhood.com/tx/0xed5e809f4bbdcd508e1a78a5fcd800b757ea43472cfa4cc289b78a2591b6fc03) |
| 43 | AMD | Embellisher | $644 million | slashed | [0x27dad3d2…6e5d8f](https://explorer.testnet.chain.robinhood.com/tx/0x27dad3d2067008072759d165a4216cea159bb7981fc1c4654880f42a646e5d8f) |
| 44 | AMD | Fabricator | $554 million | slashed | [0xbd87fcd8…1a6685](https://explorer.testnet.chain.robinhood.com/tx/0xbd87fcd8d599bba0066e769f243ab857fb05d0272248235ad10cc586c71a6685) |
| 45 | AMD | Diligent | $37 million | cleared | [0xf9fa2361…34c64c](https://explorer.testnet.chain.robinhood.com/tx/0xf9fa23615b7fa68d66db1cc5f9137009729e4d93abc46fdb55e013535f34c64c) |
| 46 | AMD | Qwen 2.5 7B (AI, replayed) | $1,095 million | cleared | [0x938e2ece…f6ae8b](https://explorer.testnet.chain.robinhood.com/tx/0x938e2eceecb7330d6c9b914b58941d129ee77531b3f8403b2ffc42be8df6ae8b) |
| 47 | AMD | Misreader | $222 million | slashed | [0xa0cb9119…c5b7b4](https://explorer.testnet.chain.robinhood.com/tx/0xa0cb9119cf0a4ed16ec527b6197dae6d6c1129fdf10b2e9420cd3b760cc5b7b4) |
| 48 | AMD | Embellisher | $39 million | slashed | [0xe5ff0666…4d9d77](https://explorer.testnet.chain.robinhood.com/tx/0xe5ff0666acaa43ab09fce3bba4ac43b1b78bb14648ad0b2333bf14c1704d9d77) |
| 49 | AMD | Fabricator | $39 million | slashed | [0xd40a73cf…c73e58](https://explorer.testnet.chain.robinhood.com/tx/0xd40a73cf7e37ae437e319642d9b8e5db58866a55f588ad45b780d70476c73e58) |
