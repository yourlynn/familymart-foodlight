#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""FamilyMart 友善食光掃描器（區域版）

功能：
- 依 config.json 內的「區域」設定，呼叫 FamilyMart 友善食光 API
- 週一～五：上班 + 家裡區域
- 週六～日：家裡區域
- 篩選區域內門市（預設 500m 內；使用 API 回傳 distance）
- 依 watchlist (關鍵字) 分類商品：白名單優先、其他商品
- 輸出 Markdown 格式報告（適合貼到 Discord）

不依賴第三方套件（僅使用 Python 標準庫）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

PRODUCT_URL = "https://stamp.family.com.tw/api/maps/MapProductInfo"


@dataclass
class Product:
    code: str
    name: str
    qty: int


@dataclass
class Store:
    old_pkey: str
    name: str
    address: str
    tel: Optional[str]
    latitude: float
    longitude: float
    distance_m: float
    products: List[Product]


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _http_json(url: str, payload: dict, timeout: float = 15.0) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "family-mart-foodlight/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def fetch_products_at_point(
    project_code: str,
    lat: float,
    lon: float,
    old_pkeys: List[str],
    timeout: float = 15.0,
) -> List[Dict[str, Any]]:
    payload = {
        "OldPKeys": old_pkeys,
        "PostInfo": "",
        "Latitude": lat,
        "Longitude": lon,
        "ProjectCode": project_code,
    }
    data = _http_json(PRODUCT_URL, payload, timeout=timeout)
    if data.get("code") != 1:
        raise RuntimeError(f"API error: {data}")
    return data.get("data", [])


def flatten_store_products(store_obj: Dict[str, Any]) -> List[Product]:
    out: List[Product] = []
    for group in store_obj.get("info", []) or []:
        for cat in group.get("categories", []) or []:
            for p in cat.get("products", []) or []:
                qty = _safe_int(p.get("qty"), 0)
                if qty <= 0:
                    continue
                out.append(
                    Product(
                        code=str(p.get("code", "")),
                        name=str(p.get("name", "")),
                        qty=qty,
                    )
                )
    out.sort(key=lambda x: (x.name, x.code))
    return out


def merge_store(existing: Store, incoming: Store) -> Store:
    dist = min(existing.distance_m, incoming.distance_m)

    by_key: Dict[Tuple[str, str], int] = {}
    for p in existing.products:
        by_key[(p.code, p.name)] = max(by_key.get((p.code, p.name), 0), p.qty)
    for p in incoming.products:
        by_key[(p.code, p.name)] = max(by_key.get((p.code, p.name), 0), p.qty)

    products = [Product(code=k[0], name=k[1], qty=v) for k, v in by_key.items() if v > 0]
    products.sort(key=lambda x: (x.name, x.code))

    return Store(
        old_pkey=existing.old_pkey,
        name=incoming.name or existing.name,
        address=incoming.address or existing.address,
        tel=incoming.tel or existing.tel,
        latitude=incoming.latitude or existing.latitude,
        longitude=incoming.longitude or existing.longitude,
        distance_m=dist,
        products=products,
    )


def get_areas_for_today(config: Dict[str, Any]) -> List[str]:
    """根據今天是週幾，選擇對應的區域"""
    schedule = config.get("schedule", {})
    weekday = dt.datetime.now().weekday()  # 0=週一, 6=週日
    
    if weekday < 5:  # 週一到週五
        return schedule.get("weekday", {}).get("areas", ["work", "home"])
    else:  # 週六週日
        return schedule.get("weekend", {}).get("areas", ["home"])


def scan_area(
    config: Dict[str, Any],
    area_key: str,
    old_pkeys: List[str],
) -> Dict[str, Store]:
    """掃描單一區域"""
    project_code = str(config.get("project", {}).get("project_code", "202106302"))
    areas = config.get("areas", {})
    area = areas.get(area_key, {})
    points = area.get("points", [])
    radius_m = float(config.get("search_radius_m", 500))

    stores: Dict[str, Store] = {}

    for pt in points:
        lat = float(pt["lat"])
        lon = float(pt["lon"])
        result = fetch_products_at_point(project_code, lat, lon, old_pkeys)
        for st in result:
            old_pkey = str(st.get("oldPKey", ""))
            if not old_pkey:
                continue

            distance_m = float(st.get("distance", 10**9))
            if distance_m > radius_m:
                continue

            incoming = Store(
                old_pkey=old_pkey,
                name=str(st.get("name", "")),
                address=str(st.get("address", "")),
                tel=str(st.get("tel")) if st.get("tel") else None,
                latitude=float(st.get("latitude") or 0.0),
                longitude=float(st.get("longitude") or 0.0),
                distance_m=distance_m,
                products=flatten_store_products(st),
            )

            if incoming.old_pkey in stores:
                stores[incoming.old_pkey] = merge_store(stores[incoming.old_pkey], incoming)
            else:
                stores[incoming.old_pkey] = incoming
                old_pkeys.append(incoming.old_pkey)

    return stores


def scan_areas(config: Dict[str, Any]) -> Dict[str, Dict[str, Store]]:
    """掃描今天需要的所有區域，回傳 {area_key: {store_key: Store}}
    
    每個區域獨立掃描，不共用 old_pkeys，避免 API 回傳結果被影響。
    """
    area_keys = get_areas_for_today(config)
    results: Dict[str, Dict[str, Store]] = {}
    
    for area_key in area_keys:
        # 每個區域獨立的 old_pkeys 列表
        old_pkeys: List[str] = []
        results[area_key] = scan_area(config, area_key, old_pkeys)
    
    return results


def split_products_by_watchlist(
    products: Iterable[Product],
    watchlist: List[str],
    blacklist: Optional[List[str]] = None,
) -> Tuple[List[Product], List[Product]]:
    wl = [str(w).strip() for w in (watchlist or []) if str(w).strip()]
    bl = [str(b).strip() for b in (blacklist or []) if str(b).strip()]

    def is_watch(p: Product) -> bool:
        if not wl:
            return False
        return any(k in p.name for k in wl)

    def is_blocked(p: Product) -> bool:
        if not bl:
            return False
        return any(k in p.name for k in bl)

    wlp: List[Product] = []
    other: List[Product] = []
    for p in products:
        if is_blocked(p):
            continue
        (wlp if is_watch(p) else other).append(p)
    return wlp, other


def render_markdown_report(
    area_results: Dict[str, Dict[str, Store]],
    config: Dict[str, Any],
    now: Optional[dt.datetime] = None,
) -> str:
    if now is None:
        now = dt.datetime.now()

    watchlist = list(config.get("watchlist") or [])
    blacklist = list(config.get("blacklist") or [])
    areas_config = config.get("areas", {})

    title_time = now.strftime("%Y/%m/%d %H:%M")
    weekday_names = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    weekday_str = weekday_names[now.weekday()]

    out: List[str] = []
    out.append(f"🌱 友善食光通知 - {title_time} ({weekday_str})")
    out.append("")

    for area_key, stores in area_results.items():
        area_info = areas_config.get(area_key, {})
        area_name = area_info.get("name", area_key)
        store_watchlist = [str(s).strip() for s in (area_info.get("store_watchlist") or []) if str(s).strip()]
        
        # 只篩選白名單店家
        def is_watchlist_store(s: Store) -> bool:
            return any(wl in s.name for wl in store_watchlist)
        
        watchlist_stores = [s for s in stores.values() if is_watchlist_store(s)]
        watchlist_stores.sort(key=lambda s: (s.distance_m, s.name))

        out.append(f"📍 {area_name}")
        out.append("")

        if not watchlist_stores:
            out.append("（白名單店家都沒有即期品）")
            out.append("")
            out.append("---")
            out.append("")
            continue

        for st in watchlist_stores:
            wlps, others = split_products_by_watchlist(st.products, watchlist, blacklist)
            
            out.append(f"🏪 {st.name}")
            
            # 白名單商品：列出名稱，用頓號分隔
            if wlps:
                wl_names = "、".join(p.name for p in wlps)
                out.append(f"⭐ 白名單商品：{wl_names}")
            else:
                out.append("⭐ 白名單商品：（無）")
            
            # 其他商品：最多顯示 3 個，其餘用「...等 N 項」
            if others:
                if len(others) <= 3:
                    other_names = "、".join(p.name for p in others)
                else:
                    other_names = "、".join(p.name for p in others[:3]) + f"...等 {len(others)} 項"
                out.append(f"📦 其他商品：{other_names}")
            else:
                out.append("📦 其他商品：（無）")
            
            out.append("")

        out.append("---")
        out.append("")

    # 移除最後的分隔線
    if out and out[-1] == "":
        out.pop()
    if out and out[-1] == "---":
        out.pop()

    return "\n".join(out).rstrip() + "\n"


def render_discover_report(
    area_results: Dict[str, Dict[str, Store]],
    config: Dict[str, Any],
) -> str:
    """探索模式：列出所有門市，方便使用者挑選 store_watchlist"""
    areas_config = config.get("areas", {})
    out: List[str] = []
    out.append("🔍 探索模式 - 附近所有全家門市")
    out.append("")
    out.append("請將想關注的門市名稱填入 config.json 的 store_watchlist")
    out.append("")

    for area_key, stores in area_results.items():
        area_info = areas_config.get(area_key, {})
        area_name = area_info.get("name", area_key)
        
        sorted_stores = sorted(stores.values(), key=lambda s: (s.distance_m, s.name))
        
        out.append(f"📍 {area_name}")
        out.append("")
        
        if not sorted_stores:
            out.append("（附近沒有友善食光門市）")
        else:
            out.append("| 門市名稱 | 距離 | 即期品數 |")
            out.append("|----------|------|----------|")
            for st in sorted_stores:
                dist_str = f"{int(st.distance_m)}m"
                out.append(f"| {st.name} | {dist_str} | {len(st.products)} 項 |")
        
        out.append("")
        out.append("---")
        out.append("")

    out.append("💡 使用方式：")
    out.append('```json')
    out.append('"store_watchlist": ["芝玉店", "新芝蘭店"]')
    out.append('```')
    
    return "\n".join(out).rstrip() + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="掃描全家友善食光（區域版）並輸出 Markdown")
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.json"))
    ap.add_argument("--out", help="輸出到檔案（預設 stdout）")
    ap.add_argument("--radius", type=float, help="覆蓋 search_radius_m")
    ap.add_argument("--watch", action="append", default=None, help="額外加入白名單關鍵字（可重複）")
    ap.add_argument("--area", action="append", default=None, help="指定區域（可重複，預設依星期自動選擇）")
    ap.add_argument("--discover", action="store_true", help="探索模式：列出所有門市，方便挑選 store_watchlist")
    args = ap.parse_args(argv)

    config = load_config(args.config)
    if args.radius is not None:
        config["search_radius_m"] = args.radius

    watchlist = list(config.get("watchlist") or [])
    if args.watch:
        watchlist.extend(args.watch)
        config["watchlist"] = watchlist

    # 如果指定了 --area，覆蓋自動選擇
    if args.area:
        # 暫時修改 schedule 讓 get_areas_for_today 回傳指定的區域
        config["schedule"] = {
            "weekday": {"areas": args.area},
            "weekend": {"areas": args.area},
        }

    # 探索模式：忽略 store_watchlist，顯示所有門市
    if args.discover:
        # 清空 store_watchlist 讓掃描回傳所有門市
        for area_key in config.get("areas", {}):
            config["areas"][area_key]["store_watchlist"] = []

    area_results = scan_areas(config)
    
    # 根據模式選擇報告格式
    if args.discover:
        report = render_discover_report(area_results, config)
    else:
        report = render_markdown_report(area_results, config)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
    else:
        sys.stdout.write(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
