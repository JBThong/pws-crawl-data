---
name: crawl-listing-fetch
description: How to fetch raw listing data (detail/price/stock) for Lazada, Shopee V2, TikTok, Zalora, Haravan, Bagisto, Mirakl — separate from crawl-order-info-fetch (order/return/transaction) because listing shape (1 call vs multiple calls for price/stock) varies a lot per platform. Use when the request is "get listing/price/stock for product X". Requires platform_id and shopfe_id to be given up front — this plugin has no database access to resolve them.
---

# Fetch raw listing data (detail / price / stock)

Kept separate from `crawl-order-info-fetch` (order/return/transaction) because listing has a fundamentally different shape per platform: some platforms return detail+price+stock in one call, others split price/stock into dedicated endpoints. Mixing this into the order-focused skill risks silently missing the extra calls for Zalora/Shopee.

This plugin has **no database access** — `platform_id` (or platform domain, e.g. `zalora.sg`), `shopfe_id`, and the marketplace item identifier (`listingSku` — see the identifier table below for what that looks like per platform) must all be given by the caller. Ask if any are missing; don't guess a platform_id for a given shopfe_id, and don't guess which identifier type (sku vs numeric id vs product-set id) a given value is.

## 1. Per-platform call table & identifier reference

See `references/listing-reference.md` for the full per-platform call table (base call, price/stock location, mandatory extra calls) and the identifier-type table — both verified against `crawler-v3-golang` parser source, not `request-maker-v5` alone.

## 2. Rule for "check stock" requests: always call everything, don't branch on conditions

When the request is specifically about stock (not just "get raw listing"), **call all stock-related endpoints for that platform unconditionally** — don't try to be clever and skip a call based on `has_model` or whether a warehouse breakdown was asked for. Simpler and avoids missing data if the condition check itself is wrong.

Concretely, for a stock check:
- **Zalora**: base + `get_product_set_stocks` (mandatory anyway).
- **Shopee V2**: base `get_item_base_info` + `get_model_list` (call both regardless of `has_model`).
- **TikTok**: base `get_listing_item` + `get_inventory` (both regular and campaign stock).
- **Haravan**: base `get_listing_item` + `get_warehouses` + `get_inventory_locations` (both aggregate and per-warehouse).
- **Lazada / Bagisto / Mirakl**: base call only (no separate stock endpoint exists).

For a plain "get listing detail" request (not stock-specific), stick to the mandatory-only column in `references/listing-reference.md` (Zalora always, Shopee only if `has_model=true` — check the base response first) to avoid unnecessary calls.

## 3. Call the script

Same tool as order fetch:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_crawl_data.py \
  --env dev|staging|prod \
  --platform-id <platformId> --shop-id <shopfeId> \
  --request-type <type> --params '<json>'
```

## 4. Reply following the `crawl-data-reply` skill

Naming convention for Option 2 (Drive): `listing_<product_id>.json` — one file per listing, same rule as orders (never combine multiple listings into one file even if fetched in one batch).
