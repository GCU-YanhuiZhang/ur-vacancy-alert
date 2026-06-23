"""UR 賃貸 后端 JSON API 客户端(实测确认 2026-06-19,纯 stdlib,无需浏览器)。

主机 chintai.r6.ur-net.go.jp;全部 POST,必须带 Referer/Origin 头。
接口与字段说明见 .scratch/ur-vacancy-alert/PRD.md「Crawler」节。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API_HOST = "https://chintai.r6.ur-net.go.jp"
EP_RESULT_MAIN = API_HOST + "/chintai/api/bukken/search/result_main/"
EP_BUKKEN = API_HOST + "/chintai/api/bukken/result/bukken_result/"
EP_ROOM = API_HOST + "/chintai/api/bukken/result/bukken_result_room/"

HEADERS = {
    "Referer": "https://www.ur-net.go.jp/",
    "Origin": "https://www.ur-net.go.jp",
    "User-Agent": "Mozilla/5.0 (ur-vacancy-alert; personal use)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


def _post(url, params, retries=3, backoff=1.5):
    body = urllib.parse.urlencode(params).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"UR API 请求失败 {url}: {last}")


def vacant_danchi_count(block, tdfk):
    """当前有空房的団地数(result_main 的 count)。"""
    data = _post(EP_RESULT_MAIN, _base(block, tdfk))
    return data.get("count")


def list_danchi(block, tdfk, page_size=50, pause=0.4):
    """枚举某都道府県的全部 UR 団地(分页),返回原始 dict 列表(去重)。"""
    out, seen = [], set()
    for page in range(0, 40):
        params = _base(block, tdfk)
        params.update({"pageSize": page_size, "pageIndex": page})
        arr = _post(EP_BUKKEN, params)
        if not isinstance(arr, list) or not arr:
            break
        for d in arr:
            key = (d.get("shisya"), d.get("danchi"), d.get("shikibetu"))
            if key not in seen:
                seen.add(key)
                out.append(d)
        if len(arr) < page_size:
            break
        time.sleep(pause)
    return out


def get_vacant_rooms(shisya, danchi, shikibetu, block="kanto", tdfk="14", pause=0.3):
    """某団地当前空房部屋的原始 dict 列表(按 pageIndexRoom 翻页,按 id 去重)。"""
    rooms, ids, total = [], set(), None
    for page in range(0, 30):
        params = _base(block, tdfk)
        params.update({
            "pageSize": 10, "pageIndex": 0,
            "shisya": shisya, "danchi": danchi, "shikibetu": shikibetu,
            "pageIndexRoom": page,
        })
        arr = _post(EP_ROOM, params)
        if not isinstance(arr, list) or not arr:
            break
        for r in arr:
            rid = r.get("id")
            if rid and rid in ids:
                continue
            if rid:
                ids.add(rid)
            rooms.append(r)
        if total is None:
            try:
                total = int(arr[0].get("allCount") or 0)
            except (ValueError, TypeError):
                total = None
        if total is not None and len(rooms) >= total:
            break
        if len(arr) < 10:
            break
        time.sleep(pause)
    return rooms


def _base(block, tdfk):
    return {
        "rent_low": "", "rent_high": "", "walk": "",
        "floorspace_low": "", "floorspace_high": "", "years": "", "mode": "",
        "block": block, "tdfk": tdfk, "rireki_tdfk": tdfk,
        "orderByField": "1", "pageSize": 10, "pageIndex": 0,
        "shisya": "", "danchi": "", "shikibetu": "", "pageIndexRoom": "0", "sp": "",
    }
