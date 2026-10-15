#!/usr/bin/env python3
"""Phase 1 test tool: fetch raw marketplace crawl data via request-maker-v5.

Calls request-maker-v5's POST /request to get a signed UrlStruct, then calls
that URL directly (bypassing crawler-v3-golang's RabbitMQ/PHP-parser pipeline
entirely), and prints the marketplace's raw response.

Self-contained: platform ids and default base URLs live in crawl_data_config.py
(same directory) instead of a companion .json/.env file, so this deploys as a
plain .py alongside its sibling and needs nothing else copied to the target host.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import crawl_data_config


def load_platform_id(platform_domain):
    for platform_id, domain in crawl_data_config.PLATFORM_IDS.items():
        if domain == platform_domain:
            return int(platform_id)
    raise ValueError(f"Unknown platform domain '{platform_domain}', see crawl_data_config.PLATFORM_IDS")


def call_request_maker(base_url, req_name, platform_id, shop_id, request_type, params):
    body = {
        req_name: {
            "platform_id": platform_id,
            "shop_id": shop_id,
            "request_type": request_type,
            "params": params or {},
        }
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/request",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_marketplace(url_struct, proxy=None):
    url = url_struct["url"]
    method = (url_struct.get("type") or "GET").upper()
    headers = url_struct.get("headers") or {}
    params = url_struct.get("params")

    if method == "GET":
        if isinstance(params, dict) and params:
            qs = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{qs}"
        req = urllib.request.Request(url, headers=headers, method="GET")
    else:
        content_type = headers.get("Content-Type", "")
        if content_type.startswith("application/json"):
            # compact, unescaped-unicode encoding to match PHP's json_encode(..., JSON_UNESCAPED_UNICODE)
            # byte-for-byte — some platforms (TikTok) sign over this exact JSON string, so any
            # whitespace/escaping difference from Python's default json.dumps breaks the signature.
            body = json.dumps(params or {}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        elif isinstance(params, str):
            # some platforms (e.g. Zalora POST) hand back an already-encoded string body
            body = params.encode("utf-8")
        elif content_type.startswith("multipart/form-data"):
            raise NotImplementedError("multipart/form-data UrlStruct not supported yet")
        else:
            body = urllib.parse.urlencode(params or {}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

    if proxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        with opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Fetch raw crawl data via request-maker-v5")
    parser.add_argument("--base-url", default=os.environ.get("REQUEST_MAKER_BASE_URL"))
    parser.add_argument("--env", choices=["dev", "staging", "prod"], help="pick base URL from crawl_data_config.DEFAULT_BASE_URLS")
    parser.add_argument("--platform-id", type=int, help="numeric platform_id, e.g. 56")
    parser.add_argument("--platform", help="platform domain from crawl_data_config.PLATFORM_IDS, e.g. zalora.sg")
    parser.add_argument("--shop-id", type=int, required=True)
    parser.add_argument("--request-type", required=True)
    parser.add_argument("--params", default="{}", help="JSON string of extra params (Config.php fields)")
    parser.add_argument(
        "--marketplace-proxy",
        default=os.environ.get("MARKETPLACE_PROXY"),
        help="HTTP(S) proxy URL (e.g. http://10.11.1.6:3128) for the marketplace call only — "
        "some marketplaces (Shopee, TikTok, likely Lazada) require a whitelisted IP. "
        "The request-maker-v5 call is never proxied (internal gateway, not whitelist-gated).",
    )
    args = parser.parse_args()

    if not args.base_url and args.env:
        args.base_url = crawl_data_config.DEFAULT_BASE_URLS.get(args.env)

    if not args.base_url:
        print("Missing --base-url / --env (or set REQUEST_MAKER_BASE_URL)", file=sys.stderr)
        sys.exit(1)

    if args.platform_id is None:
        if not args.platform:
            print("Need either --platform-id or --platform", file=sys.stderr)
            sys.exit(1)
        try:
            args.platform_id = load_platform_id(args.platform)
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(1)

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as e:
        print(f"Invalid --params JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        rm_response = call_request_maker(
            args.base_url, "req1", args.platform_id, args.shop_id, args.request_type, params
        )
    except urllib.error.HTTPError as e:
        print(f"request-maker-v5 HTTP error {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot reach request-maker-v5 at {args.base_url}: {e}", file=sys.stderr)
        sys.exit(1)

    if rm_response.get("status") != 0:
        print(f"request-maker-v5 returned error: {json.dumps(rm_response, ensure_ascii=False)}", file=sys.stderr)
        sys.exit(1)

    requests_map = rm_response.get("requests") or {}
    if not requests_map:
        print("request-maker-v5 returned no requests (check platform_id/shop_id/request_type)", file=sys.stderr)
        sys.exit(1)

    for key, link_config in requests_map.items():
        # link_config["url"] is a JSON-encoded string containing the actual UrlStruct
        url_struct = json.loads(link_config["url"])
        print(f"--- {key} ---", file=sys.stderr)
        try:
            raw = call_marketplace(url_struct, proxy=args.marketplace_proxy)
        except urllib.error.HTTPError as e:
            print(f"Marketplace HTTP error {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
            continue
        except urllib.error.URLError as e:
            print(f"Cannot reach marketplace URL: {e}", file=sys.stderr)
            continue
        print(raw)


if __name__ == "__main__":
    main()
