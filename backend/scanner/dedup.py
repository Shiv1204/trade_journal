def find_duplicates(scanner_1_results: list[dict], scanner_2_results: list[dict]) -> dict:
    scanner_1_symbols = {r["symbol"].upper() for r in scanner_1_results if "symbol" in r}
    scanner_2_symbols = {r["symbol"].upper() for r in scanner_2_results if "symbol" in r}

    only_in_1 = scanner_1_symbols - scanner_2_symbols
    only_in_2 = scanner_2_symbols - scanner_1_symbols
    in_both = scanner_1_symbols & scanner_2_symbols

    deduped_trade_list = sorted(in_both)

    def build_lookup(results):
        lookup = {}
        for r in results:
            key = r.get("symbol", "").upper()
            if key and key not in lookup:
                lookup[key] = r.get("price")
        return lookup

    lookup_1 = build_lookup(scanner_1_results)
    lookup_2 = build_lookup(scanner_2_results)

    trade_entries = []
    for symbol in deduped_trade_list:
        trade_entries.append({
            "symbol": symbol,
            "price_1": lookup_1.get(symbol),
            "price_2": lookup_2.get(symbol),
        })

    return {
        "only_in_scanner_1": sorted(only_in_1),
        "only_in_scanner_2": sorted(only_in_2),
        "in_both": sorted(in_both),
        "trade_entries": trade_entries,
        "count_only_1": len(only_in_1),
        "count_only_2": len(only_in_2),
        "count_both": len(in_both),
    }
