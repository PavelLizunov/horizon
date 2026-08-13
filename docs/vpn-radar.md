# VPN and censorship radar

Horizon treats VPN coverage as an engineering and network-measurement radar,
not as a consumer VPN-review section. The MVP has two processing profiles:

- `vpn-engineering` covers protocols, transports, releases, breaking changes,
  vulnerabilities, compatibility, distribution, and traffic-obfuscation work;
- `censorship-watch` covers measured blocking, shutdowns, throttling, active
  probing, field reports, and competing outage explanations.

Both profiles reject rankings, discounts, affiliate reviews, generic privacy
advice, configuration dumps, and unexplained single-user failures. Their score
thresholds are deliberately high: 6.5 for engineering and 7.0 for censorship.
A single field report cannot score above 5.9, regardless of country.

## MVP sources

The first production set is intentionally bounded:

- eight upstream GitHub release feeds: sing-box, Xray-core, Hysteria,
  NaiveProxy, shadowsocks-rust, Amnezia, zapret, and ByeDPI;
- the official OONI blog and reports feeds;
- four Russian field channels: `zatelecom`, `usher2`,
  `amnezia_vpn_news_ru`, and `na_svyazi_helpdesk`;
- one global GDELT query and one Russian Google News query.

Every endpoint was checked before enabling it. GitHub Releases and official
project feeds establish what an upstream published; they do not independently
prove performance or censorship-resistance claims. Telegram is a lead source,
not confirmation. OONI anomalies are signals unless the measurement and method
support the claimed mechanism.

GDELT and Google News accept arrays of query configurations. The old
single-object form remains valid and is normalized to a one-item list, so an
existing finance query can coexist with the VPN query.

## Reader-facing evidence label

VPN articles include one editorial evidence block whose first value is:

- `CONFIRMED` — reproducible measurement, matching observations in several
  independent networks, official technical confirmation, or packet evidence
  with independent repetition;
- `PROBABLE` — several independent detailed reports and no sign of a general
  outage, but the mechanism is not yet demonstrated;
- `UNVERIFIED` — a single or incomplete field signal;
- `CONTRADICTED` — stronger evidence supports an outage, software/server fault,
  stale report, or another explanation.

This model-generated label is an MVP editorial summary. The separate Evidence
Ledger continues to show its claim-level source checks on the article page.

## Deliberately deferred

The next useful layer is GitHub Issues, pull requests, and Discussions plus a
persistent incident ledger. That ledger will track country, ASN/access type,
mechanism, affected protocol, first/last observation, source count, and the
transition `UNVERIFIED → PROBABLE → CONFIRMED → RESOLVED`. Until it exists,
Horizon does not pretend that daily article deduplication is incident tracking.
