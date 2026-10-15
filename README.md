# pws-crawl-data

Claude Code plugin: fetch raw marketplace crawl data (order / listing / return / transaction / AWB) from Lazada, Shopee V2, TikTok, Zalora, Mirakl — directly through `request-maker-v5`, bypassing the crawler-v3-golang/RabbitMQ pipeline.

No database access, no credentials, no MCP server. Needs only:
- Network access to the internal `request-maker-v5` gateway (`dev`/`staging`/`prod` — see `scripts/crawl_data_config.py`).
- `platform_id` (or platform domain, e.g. `zalora.sg`) and `shopfe_id` for the shop you're querying, supplied by you — this plugin cannot look these up from just an order number.
- **IP whitelisting on some marketplaces — see Prerequisites below before assuming a failed call is a code/param bug.**

## Prerequisites: marketplace IP whitelisting

Some marketplace APIs (confirmed: Shopee, TikTok; Lazada likely too) only accept calls from a whitelisted IP. `fetch_crawl_data.py` makes the final marketplace call directly from whatever machine runs it — it does **not** go through any shared server, so each user's own machine/network needs to already be allowed, or routed through one that is. `request-maker-v5` itself is never proxied — it's an internal gateway, not whitelist-gated — only the final marketplace call needs this.

On at least one working setup, this is done with a proxy at `10.11.1.6:3128` for these hosts:

| Host | Marketplace |
|---|---|
| `partner.shopeemobile.com` | Shopee |
| `open-api.tiktokglobalshop.com` | TikTok |
| (a Lazada host — not fully captured) | Lazada |

This was read off one person's local network-proxy tool config, not from any central/shared document — treat it as a known-working example, not a complete or official list. `zalora`/`mirakl` weren't in that example; unclear if they need it too.

**If a call fails with something that looks like an auth/connection rejection despite correct `platform_id`/`shopfe_id`/params**, this is the first thing to check — ask whoever manages this proxy internally for the current host list and your own access. Two ways to use it once you have it:

1. **Script flag/env var (recommended)** — pass `--marketplace-proxy http://10.11.1.6:3128` to `fetch_crawl_data.py`, or set `export MARKETPLACE_PROXY=http://10.11.1.6:3128` once. Scoped to just the marketplace call; the `request-maker-v5` call is unaffected either way. No other setup needed.
2. **OS-level proxy rule** — route the specific marketplace hosts above through the proxy at the network/OS level (e.g. a per-domain rule in a local proxy-manager tool). `urllib` honors this automatically with no flag needed, but it's more setup (an extra app, per-domain rules to maintain) than option 1.

## Install

```bash
claude --plugin-dir /path/to/pws-crawl-data   # one-session test, no install
```

Once this repo is pushed to GitHub (or any git host), it's a self-hosted marketplace — the repo's own `.claude-plugin/marketplace.json` lists itself as a plugin, so no separate marketplace repo is needed:

```bash
claude plugin marketplace add <org>/<repo>              # GitHub shorthand
# or: claude plugin marketplace add https://gitlab.example.com/<group>/<repo>.git
claude plugin install pws-crawl-data@pws-crawl-data-marketplace
```

## Releasing an update

Auto-update is off by default — each user runs `claude plugin update pws-crawl-data@pws-crawl-data-marketplace` (or `/plugin marketplace update pws-crawl-data-marketplace` in-session) to pull the latest.

**Claude Code only fetches an update when `.claude-plugin/plugin.json`'s `version` field actually changes** — it compares the version string, not the git commit. Pushing new commits without bumping `version` means `claude plugin update` will report "already up to date" even though the code changed. **Bump `version` on every release that should reach users.**

## What's included

- `skills/crawl-order-info-fetch` — order detail, return, Shopee tracking/payout/logistics-channel, Lazada shipment trace.
- `skills/crawl-listing-fetch` — listing detail/price/stock.
- `skills/crawl-transaction-fetch` — settlement/payout by date range.
- `skills/crawl-awb-fetch` — shipping label (AWB) PDF, a multi-step flow that differs per platform.
- `skills/crawl-data-reply` — how to deliver fetched raw data back (Slack message/Canvas, Google Drive, or plain text).
- `scripts/fetch_crawl_data.py` + `scripts/crawl_data_config.py` — the actual fetch tool the skills call.

## Usage

Just ask, in your own Claude Code session with this plugin installed:

> "Get raw order data for order 586239890406999636, shopfe_id 84140, TikTok Indonesia, prod"

The relevant skill picks the right `request_type`/params for the platform and calls `scripts/fetch_crawl_data.py` directly. See each `skills/<name>/SKILL.md` for the platform-specific details and gotchas.

## Why no database / MCP connector

Earlier iterations resolved `shopfe_id`/`platform_id` from an order number via a DB lookup (an MCP server reading PowerSell's MySQL). That requires every installer to have their own DB credentials and a locally-running server — fragile and a real access-control question for something meant to be shared broadly. Since `platform_id` is also required anyway (it isn't derivable from a shopfe_id without a DB hop, and differs per country even for the same marketplace brand — e.g. TikTok Indonesia=403 vs Thailand=405), dropping the DB lookup and requiring both fields explicit removes the dependency entirely: this plugin only needs network access to `request-maker-v5`, nothing else.
