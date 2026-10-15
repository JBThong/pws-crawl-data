---
name: crawl-transaction-fetch
description: How to fetch raw transaction/settlement/payout data for Lazada, Shopee V2, TikTok, Zalora — separate from crawl-order-info-fetch (order/return) because the correct request_type per platform does NOT match what its name suggests, and the query shape is date-range based rather than order-number based. Use when the request is "get transactions/settlement/payout for shop X" or "get transaction for order Y". Requires platform_id and shopfe_id to be given up front — this plugin has no database access to resolve them.
---

# Fetch raw transaction data

Kept separate from `crawl-order-info-fetch` because transaction breaks both assumptions that hold for order/return:

1. **Query shape is different.** Order/return are point lookups by a known order_number/return_number. Transaction is fundamentally a **date-range list** (`pagination_info.updated_from/updated_to`) — only Lazada supports narrowing to one order on top of that, and even then a date range is still required. If a request just gives an order number ("get transaction for order X") without a date range, ask for one (or default to a recent window) before calling anything.
2. **The obvious request_type name is wrong for 3 of 4 platforms.** `get_wallet_transaction_list` exists on every platform below and *sounds* like the right call — it silently returns the wrong concept (or an unrelated one) on Lazada, Shopee, and TikTok. This was found by reading the actual `parse_get_transactions` parser code, not by guessing from method names — don't reintroduce the mistake by trusting naming symmetry.

This plugin has **no database access** — `platform_id` (or platform domain) and `shopfe_id` must be given by the caller; ask if missing rather than guessing.

## Per-platform: what to actually call

See `references/transaction-request-types.md` for the full per-platform request_type/endpoint/param table.

## Call the script

Same tool as order/listing fetch — for TikTok, this means two separate invocations (statements, then statement_transactions with the ids from the first call's response):
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_crawl_data.py \
  --env dev|staging|prod \
  --platform-id <platformId> --shop-id <shopfeId> \
  --request-type <type> --params '<json>'
```

## Reply following the `crawl-data-reply` skill

Transaction results are typically a list over a date range rather than one item — if uploading to Drive, still split per logical unit (e.g. Zalora/Lazada per transaction record isn't practical; use `order_<order_id>_transaction.json` only when the request was scoped to one specific order via the optional order filter, otherwise a single dated file for the whole range is reasonable — use judgment, this wasn't a case covered by the existing one-file-per-order convention).
