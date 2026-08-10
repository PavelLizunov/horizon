# Horizon

Your own AI news radar. It collects from Hacker News, RSS, Reddit, Telegram,
Twitter/X, GitHub, OpenBB and YouTube, scores and deduplicates what it finds,
researches the background, and delivers a daily briefing.

A maintained fork of [Thysrael/Horizon](https://github.com/Thysrael/Horizon) (MIT).
Three things are this fork's own:

- **YouTube as a source.** Channel videos become timestamped transcripts —
  subtitles first, on-device Whisper if there are none, a vision model reading
  storyboard frames if there is no audio worth transcribing. Nothing is scored
  from a title. See [docs/video-source.md](docs/video-source.md).
- **A published site.** The digest is rendered by MkDocs Material and shipped to
  an ingress; chat delivery carries headlines that deep-link into it, because a
  full digest does not fit in a message and is rejected rather than truncated.
- **Narration.** Every published article gets a Russian voice track, generated
  locally, graded by a second model that transcribes it back, and linked from
  the page with a player. See [docs/narration.md](docs/narration.md).

## How it works

```
config ─┐
        ├─ fetch ─ deduplicate ─ score & filter ─ enrich ─ summarize ─┬─ site ─ narration
sources ┘                                                            ├─ email
                                                                     ├─ webhooks
                                                                     └─ MCP
```

1. **Define** — sources, processing profiles, models, languages, delivery.
2. **Fetch** — every configured source, concurrently.
3. **Deduplicate** — the same story told on three platforms becomes one item.
4. **Analyze and filter** — each item is scored by its profile's prompt against
   your threshold.
5. **Enrich** — the profile's content blocks, each using only the tools it is
   allowed.
6. **Summarize** — titles, leads, sections and cited sources, in your language.
7. **Deliver** — site, email, webhooks, MCP, or plain files.

## Quick start

### Install

```bash
git clone https://github.com/PavelLizunov/horizon.git
cd horizon
uv sync                  # add --extra dev for pytest and friends
```

`dev` is an optional extra, so development dependencies need `uv sync --extra dev`.
The OpenBB financial source has its own extra; if it pulls packages without
wheels for your machine, install the SDK with binaries only:

```bash
uv sync --extra openbb
uv pip install --only-binary=:all: openbb openbb-benzinga
```

Docker works too. Extras go in at build time, comma-separated
(`EXTRAS=trafilatura,openbb`); the `twitter` extra additionally needs a
Playwright browser and system packages the Dockerfile does not install.

```bash
docker compose build --build-arg EXTRAS=trafilatura horizon
```

### Configure

The wizard asks what you are interested in and writes `data/config.json`:

```bash
uv run horizon-wizard
```

By hand instead:

```bash
cp .env.example .env                          # API keys go here
cp data/config.example.json data/config.json  # sources go here
```

A minimal configuration:

```jsonc
{
  "ai": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key_env": "OPENAI_API_KEY"
  },
  "sources": {
    "rss": [
      {
        "name": "Simon Willison",
        "url": "https://simonwillison.net/atom/everything/",
        "profile": "tech-news"
      }
    ]
  },
  "processing": {
    "profiles_dir": "profiles",
    "default_profile": "tech-news",
    "profile_settings": {
      "tech-news": { "threshold": 7.0, "topic_dedup": true }
    }
  }
}
```

`api_key_env` is the *name* of an environment variable, never the key itself —
the real secret belongs in `.env`. Any string in the config can reference the
environment as `${VAR_NAME}`, which is how private feed URLs and webhook
endpoints stay out of the file.

A source's `profile` may name one profile, be omitted or set to `"auto"` to let
the model match it against all of them, or list several to restrict the match.
Per-profile preferences such as thresholds live in `processing.profile_settings`,
not in the profile files themselves.

`digest.max_items` and `digest.category_groups` cap the briefing and stop one
category from crowding out the rest; limits apply after filtering and before
enrichment. Full reference in the [Configuration Guide](docs/configuration.md).

### Run

```bash
uv run horizon --hours 24        # or: docker compose run --rm horizon --hours 24
```

| Option | Default | What it does |
|--------|---------|--------------|
| `--hours N` | 24 | how far back to fetch |
| `-d`, `--data-dir PATH` | `data` | state directory: summaries, subscribers, config |
| `-c`, `--config PATH` | `<data-dir>/config.json` | config file alone |
| `-l`, `--log-level LEVEL` | `WARNING` | DEBUG / INFO / WARNING / ERROR / CRITICAL |

The briefing lands in `data/summaries/`. To schedule it, see
[deploy/README.md](deploy/README.md) — on the deployed box launchd calls
`deploy/run-daily.sh`, which runs the pipeline, narrates what it published, then
builds and ships the site.

## Sources

| Source | What it fetches | Comments |
|--------|-----------------|----------|
| Hacker News | top stories by score | yes |
| RSS / Atom | any feed | — |
| Reddit | subreddits and user posts | yes |
| Telegram | public channel messages | — |
| Twitter / X | tweets from named users | yes |
| GitHub | user events, repo releases | — |
| OpenBB | company news by watchlist | — |
| YouTube | new channel videos, as transcripts | — |

## Delivery

| Channel | What it does |
|---------|--------------|
| Site | renders the digest with MkDocs Material and ships it to an ingress |
| Email | SMTP/IMAP newsletter, handling subscribe and unsubscribe itself |
| Webhooks | templated results to Feishu, DingTalk, Slack, Discord, or your own endpoint |
| MCP | exposes each pipeline stage as a tool for AI assistants |

## Documentation

| Guide | What is in it |
|-------|---------------|
| [Configuration](docs/configuration.md) | providers, sources, profiles, filtering, email, webhooks, MCP |
| [Pipeline](docs/pipeline.md) | the seven stages mapped to the code that runs them |
| [Processing profiles](docs/profiles.md) | routing, prompts, enrichment blocks, tools |
| [Scoring](docs/scoring.md) | how items are ranked |
| [Scrapers](docs/scrapers.md) | per-source detail and how to add one |
| [Video source](docs/video-source.md) | transcripts, ASR, vision fallback, anti-bot notes |
| [Narration](docs/narration.md) | the speech pipeline, its checks, and the models tried and rejected |
| [Extractors](docs/extractors.md) | full-article extraction for RSS |
| [Deployment](deploy/README.md) | scheduled runs, building and shipping the site |
| [Agent guide](AGENTS.md) | working norms, invariants and secrets policy |
| [MCP tools](src/mcp/README.md) | tool reference for MCP clients |

## Status

Runs in production daily: multi-source collection, profile-driven analysis and
enrichment, deduplication, comment summaries, localized generation, narration,
site publication, and webhook and email delivery. Tests are offline and run on
every push.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), and [AGENTS.md](AGENTS.md) for the
working norms and the secrets policy every change has to follow.

## License

[MIT](LICENSE)
