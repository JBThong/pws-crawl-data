# Listing call table & identifier reference

Verified against `crawler-v3-golang` parser source (not `request-maker-v5` alone). File:line references below point into that repo — this plugin doesn't bundle it, so they're citations for someone with that repo checked out, not resolvable links.

## Per-platform call table

For each platform: the request-maker-v5 `request_type` **and** the underlying real marketplace endpoint (method/params) — keep both so this still works if ever reimplemented directly against the marketplace API without request-maker-v5.

| Platform | Base call (detail) | Price location | Stock location | Extra call mandatory? |
|---|---|---|---|---|
| **Lazada** | `get_listing_item_by_item_id` → GET `/product/item/get` (`item_id` or `seller_sku`) | in response, each `Skus[].price` | in response, `Skus[].quantity` | No |
| **Shopee V2** | `get_listing_item` → GET `/api/v2/product/get_item_base_info` (`item_id_list`) | only when `has_model=false`; if `has_model=true`, price is in `get_model_list` → GET `/api/v2/product/get_model_list` (`item_id`) per model | same as price | **Conditional**: only when `has_model=true` |
| **TikTok** | `get_listing_item` → GET `/product/{ver}/products/{id}` | `skus[].price.sale_price` — already in base response (`TikTokApiParser_GetListing.php:522` in `crawler-v3-golang`) | `skus[].inventory[].quantity` — already in base response (`:520`) | No, for regular sellable stock. `get_inventory` → POST `/product/{ver}/inventory/search` (`product_ids`/`sku_ids`) is only for **campaign/creator stock** (promotion-specific), a different number, not more-authoritative base stock (`:791-852`) |
| **Zalora** | `get_single_product_by_sku` (GET `/v2/product/shop-sku/{sku}`) or by product-set id + `get_product_set_products` (GET `/v2/product-set/{id}/products`) | **not in base** — separate `get_product_set_prices` → GET `/v2/product-set/{id}/prices` | **not in base** — separate `get_product_set_stocks` → GET `/v2/stock/product-set/{id}` | **Yes, always** — confirmed in `ZaloraApiParser_GetListing.php:145-149,258-261` in `crawler-v3-golang` (also calls `get_product_set_images` for medias, not needed for price/stock) |
| **Haravan** | `get_listing_item` → GET `/com/products.json?ids=...` | `variants[].price` — already in base response | `variants[].inventory_quantity` (aggregate total) — already in base response | No, for the total number. `get_warehouses` + `get_inventory_locations` → GET `/com/inventory_locations.json` (`variant_ids`, `location_ids`) only needed for **per-warehouse breakdown**; code falls back to `inventory_quantity` when not called ([HaravanApiParser_GetListings.php:360-415](../../../../cmd/worker/parsers-php/parsers/HaravanApiParser/HaravanApiParser_GetListings.php:360)) |
| **Bagisto** | `get_listing_item` → GET `{API_PRODUCTS}/{id}` | `product.price`/`product.special_price` — already in base response | `product.inventories` (summed) — already in base response | No |
| **Mirakl** | `get_listing_item` → GET `/api/products/offers` (`product_ids`, batch 100) | `offer.all_prices[].unit_origin_price`/`unit_discount_price` — already in base response | `offer.quantity` — already in base response | No |

> ⚠️ **request-maker-v5 input param gotcha (Shopee only, learned the hard way — don't repeat):** `make_get_listing_item`/`make_get_model_list` read `$requestConfigParams->listingIdObject` (array of `{"sku": "<item_id>"}` objects) — **not** `scProductNumber` and not the marketplace API's own `item_id_list` param name. Calling with `scProductNumber` silently returns "no requests" (looks like a dead request_type, isn't). So for Shopee, pass `--params '{"listingIdObject": [{"sku": "<item_id>"}]}'` to `fetch_crawl_data.py`, while every other platform in this table uses `scProductNumber` (a plain array of ids/skus) for the same purpose.

## What identifier does each platform actually expect in `listingSku` (= `listing.sku`)?

`listing.sku` is always what request-maker-v5 wants, but *what that value looks like* differs per platform — matters when the resolved `listingSku` doesn't seem to match what you'd expect for that marketplace:

| Platform | request-maker-v5 param | Identifier type in `listing.sku` |
|---|---|---|
| Lazada | `scProductNumber` (array) + `auxiliary` = `item_id` (default) or `seller_sku` | Lazada `item_id` by default — set `auxiliary: "seller_sku"` if the value is actually the seller's own sku |
| Shopee V2 | `listingIdObject: [{"sku": ...}]` — see gotcha above | Shopee's numeric `item_id` |
| TikTok | `scProductNumber` (array) | TikTok's numeric product `id` |
| Zalora | `scProductNumber` (array) — but which function depends on which id: `get_single_product_by_sku` for the seller's **shop-sku**, `get_single_product_set`/`get_product_set_products` for Zalora's own **product-set id** | Ambiguous — shop-sku and product-set id are different values; `listing.sku` here is the product-set id, so default to the `product_set` functions unless the user explicitly gives a shop-sku |
| Haravan | `scProductNumber` → `ids` | Haravan's numeric product id. **No sku-based lookup exists** in the request template — if the value in hand is a sku string rather than this numeric id, there's no direct single-item fetch; would need to page through `get_listings` and filter, impractical for one item |
| Bagisto | `scProductNumber` → path `/{id}` | Bagisto's numeric product id — same limitation as Haravan, no sku-based single-item lookup |
| Mirakl | `scProductNumber` → `product_ids` | Mirakl's `product_sku` — matches `listing.sku` directly, no ambiguity |
