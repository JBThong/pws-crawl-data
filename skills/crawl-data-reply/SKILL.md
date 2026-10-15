---
name: crawl-data-reply
description: How to reply in Slack with raw crawl data fetched via crawl-order-info-fetch/crawl-listing-fetch/crawl-transaction-fetch/crawl-awb-fetch (order/listing/return/transaction/AWB from a marketplace). Use whenever posting a fetched raw data payload back to a Slack channel/DM/thread.
---

# Reply with raw crawl data in Slack

**Never trim, abridge, truncate, or paraphrase the raw JSON — send it complete, byte-for-byte, no matter how long a field is.** This applies to every delivery option below, including the plain-message one: if the full JSON doesn't fit a Slack message, that's a reason to escalate to Canvas or Drive (both exist exactly for this), never a reason to shorten the content itself. Oversized delivery is a channel problem, solved by picking a bigger channel — it is never a content problem to be solved by cutting data. This holds even when the raw payload has long/noisy fields (marketing description text, big arrays, deeply nested objects) that look safe to drop — don't decide on the user's behalf that a field doesn't matter; they asked for raw data specifically because they want to see everything the marketplace returned, not a curated subset.

After fetching raw data (via `fetch_crawl_data.py`), **ask the user which delivery option to use before posting anything** — do not assume:

- **Option 1 — Direct in Slack** (existing flow, section below)
- **Option 2 — Google Drive upload + link** (section below)

If neither a Slack nor a Drive connector is available in the current session, just print the raw JSON directly in the response instead — same no-trimming rule applies.

## Option 1 — Direct in Slack

Post the result following this decision order — try each step only if the previous one doesn't fit:

1. **Plain message (default)** — `slack_send_message` with a short summary (status/key business fields of the order — see "Common to both options" for what belongs here) followed by the raw JSON in a fenced ` ```json ` code block. Slack caps each message at ~5000 chars; if the whole message (summary + JSON) fits, stop here. This is the most readable option — prefer it whenever possible.
2. **Canvas (fallback only)** — if the JSON alone is too long for one message, do **not** split across multiple sequential messages/thread replies (harder to read, disjointed). Instead create a `slack_create_canvas` document containing the summary + full JSON in one code block, then send **one** short plain message linking to the canvas.

Never do both (redundant), and never fall back to splitting into N messages — that option was tried and rejected as harder to read than either alternative above.

## Option 2 — Google Drive upload + link

Use the Drive connector (`create_file`/`share_file`/`get_file_metadata`) to upload into a shared "Raw data" folder (ask the user for the folder id if one hasn't been established yet):

1. **File naming, one file per order — never combine multiple orders into one file, even if they were fetched together in one batched API call** (e.g. multiple orders from the same shop batched into a single `get_orders_items` call to save requests — still split the response's `order_list` back out into one Drive file per order):
   - Order: `order_<order_id>.json`
   - Return: `order_<order_id>_return.json`
   - Transaction: `order_<order_id>_transaction.json`
   - Listing: `listing_<product_id>.json`
2. `create_file` per file with the `title` above, `parentId` = the folder from above, `contentMimeType: application/json`, `disableConversionToGoogleType: true` (keep it a plain JSON file, don't convert to Google Docs). `textContent` = one compact header comment line + that single order's raw JSON — **keep the header to just the identifiers, nothing else**:
   ```
   // order_number <id>: platformId <platformId> (<platform name>), shopfeId <shopfeId>
   {...raw JSON...}
   ```
   Don't add the resolution-chain trace or a separate status line inside the file — the header above is the only thing that goes in the file besides the raw JSON itself.
3. If the destination is **not** the requester themself (e.g. sharing with a colleague), `share_file` each file with that person's email (look it up via `slack_search_users`/`slack_read_user_profile` if not already known) and `role: reader`. Skip this when sending to the requester's own DM — they already own the file.
4. Send **one** short plain Slack message listing all the summary lines + Drive file links (no raw JSON inline). For a batch, one message with one line per order/link is fine — do not send a separate message per file.

This solves the 5000-char limit the same as Canvas, plus gives a link usable outside Slack. It does **not** change the privacy consideration for third-party recipients — the same customer PII (name/phone/address) still reaches them, just via a link instead of inline text. Use judgment (or the redact-before-send approach) the same way you would for Option 1 when the recipient is someone other than the requester.

## Common to both options

**The summary is business content only — never mention how the data was fetched.** This goes to other people (colleagues, requesters), not just the requester's own internal tooling context, so don't expose the retrieval mechanics: no `fetch_crawl_data.py`, request_type names, or similar — none of that means anything to the reader and it leaks internal implementation for no reason.

Lead with the same compact identifier line used in the Drive file header (harmless, not "how it was fetched" — just which order/shop this is), then the business content: order number, status, product/item name, amount. For a batch, one such block per order.

```
order_number 585603643507442830: platformId 405 (TikTok Thailand), shopfeId 83898
DELIVERED — Colgate Optic White Vitamin C Toothpaste 80g (x1), 144.66 THB
```
