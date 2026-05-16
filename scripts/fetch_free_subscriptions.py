import base64
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)

OUT_FILE = PUBLIC / "sub.txt"
OUT_RAW_FILE = PUBLIC / "sub_raw.txt"
OUT_V2RAY_FILE = PUBLIC / "sub_v2ray.txt"
OUT_V2RAY_RAW_FILE = PUBLIC / "sub_v2ray_raw.txt"
OUT_HY2_FILE = PUBLIC / "sub_hysteria.txt"
OUT_HY2_RAW_FILE = PUBLIC / "sub_hysteria_raw.txt"
OUT_CLASH_FILE = PUBLIC / "sub_clash.yaml"
OUT_REGIONS_FILE = PUBLIC / "sub_regions.json"

SOURCES = [
    "https://raw.githubusercontent.com/awesome-vpn/awesome-vpn/master/all",
    "https://raw.githubusercontent.com/shaoyouvip/free/refs/heads/main/base64.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
]

LINK_RE = re.compile(r"(?im)^(?:vmess|vless|trojan|ss|ssr|hy2|hysteria2|hysteria)://\S+$")
V2RAY_SCHEMES = {"vmess", "vless", "trojan", "ss", "ssr", "hysteria2", "hy2", "hysteria"}
HY2_SCHEMES = {"hysteria2", "hy2", "hysteria"}

# Country detection: node name patterns → ISO 3166-1 alpha-2 code
COUNTRY_PATTERNS = [
    (r"(?:^|[/#\|\s])(?:日本|东京|大阪|Japan|Tokyo|Osaka|JP)(?:[/#\|\s_]|$)", "JP"),
    (r"(?:^|[/#\|\s])(?:美国|纽约|洛杉矶|硅谷|圣何塞|西雅图|芝加哥|达拉斯|Atlanta|Atl|Ashburn|America|USA?|United\s*States|New\s*York|Los\s*Angeles|San\s*Jose|Seattle|Chicago|Dallas|Miami)(?:[/#\|\s_]|$)", "US"),
    (r"(?:^|[/#\|\s])(?:新加坡|狮城|Singapore|SG)(?:[/#\|\s_]|$)", "SG"),
    (r"(?:^|[/#\|\s])(?:韩国|首尔|釜山|Korea|Seoul|Busan|KR)(?:[/#\|\s_]|$)", "KR"),
    (r"(?:^|[/#\|\s])(?:香港|Hong\s*Kong|HK)(?:[/#\|\s_]|$)", "HK"),
    (r"(?:^|[/#\|\s])(?:台湾|台北|Taiwan|Taipei|TW)(?:[/#\|\s_]|$)", "TW"),
    (r"(?:^|[/#\|\s])(?:德国|柏林|法兰克福|慕尼黑|Germany|Berlin|Frankfurt|Munich|DE)(?:[/#\|\s_]|$)", "DE"),
    (r"(?:^|[/#\|\s])(?:英国|伦敦|曼彻斯特|United\s*Kingdom|UK|London|Manchester|GB)(?:[/#\|\s_]|$)", "GB"),
    (r"(?:^|[/#\|\s])(?:法国|巴黎|France|Paris|FR)(?:[/#\|\s_]|$)", "FR"),
    (r"(?:^|[/#\|\s])(?:荷兰|阿姆斯特丹|Netherlands|Amsterdam|NL)(?:[/#\|\s_]|$)", "NL"),
    (r"(?:^|[/#\|\s])(?:加拿大|多伦多|温哥华|蒙特利尔|Canada|Toronto|Vancouver|Montreal|CA)(?:[/#\|\s_]|$)", "CA"),
    (r"(?:^|[/#\|\s])(?:澳大利亚|澳洲|悉尼|墨尔本|Australia|Sydney|Melbourne|AU)(?:[/#\|\s_]|$)", "AU"),
    (r"(?:^|[/#\|\s])(?:印度|孟买|India|Mumbai|Delhi|IN)(?:[/#\|\s_]|$)", "IN"),
    (r"(?:^|[/#\|\s])(?:日本|东京|Japan|Tokyo|JP)(?:[/#\|\s_]|$)", "JP"),  # duplicate, keep
    (r"(?:^|[/#\|\s])(?:意大利|Italy|Milan|Rome|IT)(?:[/#\|\s_]|$)", "IT"),
    (r"(?:^|[/#\|\s])(?:西班牙|Spain|Madrid|Barcelona|ES)(?:[/#\|\s_]|$)", "ES"),
    (r"(?:^|[/#\|\s])(?:俄罗斯|莫斯科|Russia|Moscow|RU)(?:[/#\|\s_]|$)", "RU"),
    (r"(?:^|[/#\|\s])(?:巴西|Brazil|BR)(?:[/#\|\s_]|$)", "BR"),
    (r"(?:^|[/#\|\s])(?:瑞典|Sweden|Stockholm|SE)(?:[/#\|\s_]|$)", "SE"),
    (r"(?:^|[/#\|\s])(?:瑞士|Switzerland|Zurich|CH)(?:[/#\|\s_]|$)", "CH"),
    (r"(?:^|[/#\|\s])(?:阿联酋|迪拜|UAE|Dubai|AE)(?:[/#\|\s_]|$)", "AE"),
    (r"(?:^|[/#\|\s])(?:土耳其|Turkey|Istanbul|TR)(?:[/#\|\s_]|$)", "TR"),
    (r"æ¥æ¬|Tokyo|Japan|[|#]JP[|\s_#]|🇯🇵", "JP"),
    (r"United\s*States|America|[|#]US[|\s_#]|🇺🇸", "US"),
    (r"Singapore|[|#]SG[|\s_#]|🇸🇬", "SG"),
    (r"Korea|[|#]KR[|\s_#]|🇰🇷", "KR"),
    (r"Hong\s*Kong|[|#]HK[|\s_#]|🇭🇰", "HK"),
    (r"Taiwan|[|#]TW[|\s_#]|🇹🇼", "TW"),
    (r"Germany|[|#]DE[|\s_#]|🇩🇪", "DE"),
    (r"United\s*Kingdom|[|#]UK[|\s_#]|[|#]GB[|\s_#]|🇬🇧", "GB"),
    (r"France|[|#]FR[|\s_#]|🇫🇷", "FR"),
    (r"Netherlands|[|#]NL[|\s_#]|🇳🇱", "NL"),
    (r"Canada|[|#]CA[|\s_#]|🇨🇦", "CA"),
    (r"Australia|[|#]AU[|\s_#]|🇦🇺", "AU"),
    (r"India|[|#]IN[|\s_#]|🇮🇳", "IN"),
    (r"China|[|#]CN[|\s_#]|🇨🇳|中国|北京|上海|安徽|深圳|广州", "CN"),
    (r"Indonesia|[|#]ID[|\s_#]|🇮🇩", "ID"),
    (r"Thailand|[|#]TH[|\s_#]|🇹🇭", "TH"),
    (r"Vietnam|[|#]VN[|\s_#]|🇻🇳", "VN"),
    (r"Malaysia|[|#]MY[|\s_#]|🇲🇾", "MY"),
    (r"Philippines|[|#]PH[|\s_#]|🇵🇭", "PH"),
    (r"Finland|Helsinki|[|#]FI[|\s_#]|🇫🇮|芬兰|赫尔辛基", "FI"),
    (r"Moldova|Mold[ao]va|[|#]MD[|\s_#]|🇲🇩|摩尔多瓦", "MD"),
    (r"Morocco|Morroco|[|#]MA[|\s_#]|🇲🇦|摩洛哥", "MA"),
    (r"Norway|[|#]NO[|\s_#]|🇳🇴|挪威", "NO"),
    (r"Poland|[|#]PL[|\s_#]|🇵🇱|波兰", "PL"),
    (r"Belgium|[|#]BE[|\s_#]|🇧🇪|比利时", "BE"),
    (r"Austria|[|#]AT[|\s_#]|🇦🇹|奥地利", "AT"),
    (r"Portugal|[|#]PT[|\s_#]|🇵🇹|葡萄牙", "PT"),
    (r"Mexico|[|#]MX[|\s_#]|🇲🇽|墨西哥", "MX"),
    (r"Argentina|[|#]AR[|\s_#]|🇦🇷|阿根廷", "AR"),
    (r"Chile|[|#]CL[|\s_#]|🇨🇱|智利", "CL"),
    (r"Colombia|[|#]CO[|\s_#]|🇨🇴|哥伦比亚", "CO"),
    (r"South\s*Africa|[|#]ZA[|\s_#]|🇿🇦|南非", "ZA"),
    (r"Ireland|[|#]IE[|\s_#]|🇮🇪|爱尔兰|都柏林|Dublin", "IE"),
    (r"Czech|[|#]CZ[|\s_#]|🇨🇿|捷克", "CZ"),
    (r"Romania|[|#]RO[|\s_#]|🇷🇴|罗马尼亚", "RO"),
    (r"Ukraine|[|#]UA[|\s_#]|🇺🇦|乌克兰", "UA"),
    (r"Denmark|[|#]DK[|\s_#]|🇩🇰|丹麦", "DK"),
    (r"Hungary|[|#]HU[|\s_#]|🇭🇺|匈牙利", "HU"),
    (r"Egypt|[|#]EG[|\s_#]|🇪🇬|埃及", "EG"),
    (r"Israel|[|#]IL[|\s_#]|🇮🇱|以色列", "IL"),
    (r"New\s*Zealand|[|#]NZ[|\s_#]|🇳🇿|新西兰", "NZ"),
]

COUNTRY_NAMES = {
    "JP": "日本", "US": "美国", "SG": "新加坡", "KR": "韩国",
    "HK": "香港", "TW": "台湾", "DE": "德国", "GB": "英国",
    "FR": "法国", "NL": "荷兰", "CA": "加拿大", "AU": "澳大利亚",
    "IN": "印度", "IT": "意大利", "ES": "西班牙", "RU": "俄罗斯",
    "BR": "巴西", "SE": "瑞典", "CH": "瑞士", "AE": "阿联酋",
    "TR": "土耳其", "CN": "中国", "ID": "印尼", "TH": "泰国",
    "VN": "越南", "MY": "马来西亚", "PH": "菲律宾",
    "FI": "芬兰", "MD": "摩尔多瓦", "MA": "摩洛哥", "NO": "挪威",
    "PL": "波兰", "BE": "比利时", "AT": "奥地利", "PT": "葡萄牙",
    "MX": "墨西哥", "AR": "阿根廷", "CL": "智利", "CO": "哥伦比亚",
    "ZA": "南非", "IE": "爱尔兰", "CZ": "捷克", "RO": "罗马尼亚",
    "UA": "乌克兰", "DK": "丹麦", "HU": "匈牙利", "EG": "埃及",
    "IL": "以色列", "NZ": "新西兰",
}

EMOJI_FLAGS = {
    "JP": "🇯🇵", "US": "🇺🇸", "SG": "🇸🇬", "KR": "🇰🇷",
    "HK": "🇭🇰", "TW": "🇹🇼", "DE": "🇩🇪", "GB": "🇬🇧",
    "FR": "🇫🇷", "NL": "🇳🇱", "CA": "🇨🇦", "AU": "🇦🇺",
    "IN": "🇮🇳", "IT": "🇮🇹", "ES": "🇪🇸", "RU": "🇷🇺",
    "BR": "🇧🇷", "SE": "🇸🇪", "CH": "🇨🇭", "AE": "🇦🇪",
    "TR": "🇹🇷", "CN": "🇨🇳", "ID": "🇮🇩", "TH": "🇹🇭",
    "VN": "🇻🇳", "MY": "🇲🇾", "PH": "🇵🇭",
    "FI": "🇫🇮", "MD": "🇲🇩", "MA": "🇲🇦", "NO": "🇳🇴",
    "PL": "🇵🇱", "BE": "🇧🇪", "AT": "🇦🇹", "PT": "🇵🇹",
    "MX": "🇲🇽", "AR": "🇦🇷", "CL": "🇨🇱", "CO": "🇨🇴",
    "ZA": "🇿🇦", "IE": "🇮🇪", "CZ": "🇨🇿", "RO": "🇷🇴",
    "UA": "🇺🇦", "DK": "🇩🇰", "HU": "🇭🇺", "EG": "🇪🇬",
    "IL": "🇮🇱", "NZ": "🇳🇿",
}


def fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "cf-sub-auto/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore").replace("\r", "").strip()


def maybe_base64_decode(text: str) -> str:
    compact = "".join(text.split())
    if not compact:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]+", compact):
        return text
    pad = "=" * ((4 - len(compact) % 4) % 4)
    for variant in (compact, compact.replace("-", "+").replace("_", "/")):
        try:
            decoded = base64.b64decode(variant + pad, validate=False).decode("utf-8", errors="ignore")
            if decoded and "://" in decoded:
                return decoded.replace("\r", "").strip()
        except Exception:
            pass
    return text


def extract_links(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if LINK_RE.match(line.strip())]


def detect_country(link: str) -> str | None:
    """Detect country from node name fragment (after #). Handles URL-encoded CN names and emoji flags."""
    fragment = ""
    if "#" in link:
        fragment = link.rsplit("#", 1)[-1]
    # URL-decode the fragment (many node names are percent-encoded)
    decoded = urllib.parse.unquote(fragment)
    text = fragment + " " + decoded  # search both raw and decoded
    text_upper = text.upper()

    # 1. Emoji flag + 2-letter code: 🇸🇬SG, 🇺🇸US, 🇯🇵JP, 🇩🇪DE, etc.
    m = re.search(r"[\U0001F1E6-\U0001F1FF]{2}\s*([A-Z]{2})", text)
    if m and m.group(1) in COUNTRY_NAMES:
        return m.group(1)

    # 2. Standalone 2-letter code at word boundary
    for code in COUNTRY_NAMES:
        if re.search(rf"(?:^|[|_\s#\-]){code}(?:[|_\s#\-]|$)", text_upper):
            return code

    # 3. Pattern matching (Chinese + English country names)
    for pattern, code in COUNTRY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return code
    return None


def main() -> None:
    all_links: list[str] = []
    for url in SOURCES:
        content = fetch_text(url)
        decoded = maybe_base64_decode(content)
        links = extract_links(decoded)
        all_links.extend(links)
        print(f"source={url} links={len(links)}")

    deduped = sorted(set(all_links))
    v2ray_links = [x for x in deduped if x.split("://", 1)[0].lower() in (V2RAY_SCHEMES - HY2_SCHEMES)]
    hy2_links = [x for x in deduped if x.split("://", 1)[0].lower() in HY2_SCHEMES]

    # Write raw and base64 outputs
    raw_all = "\n".join(deduped)
    raw_v2ray = "\n".join(v2ray_links)
    raw_hy2 = "\n".join(hy2_links)

    OUT_RAW_FILE.write_text(raw_all, encoding="utf-8")
    OUT_FILE.write_text(base64.b64encode(raw_all.encode("utf-8")).decode("utf-8"), encoding="utf-8")
    OUT_V2RAY_RAW_FILE.write_text(raw_v2ray, encoding="utf-8")
    OUT_V2RAY_FILE.write_text(base64.b64encode(raw_v2ray.encode("utf-8")).decode("utf-8"), encoding="utf-8")
    OUT_HY2_RAW_FILE.write_text(raw_hy2, encoding="utf-8")
    OUT_HY2_FILE.write_text(base64.b64encode(raw_hy2.encode("utf-8")).decode("utf-8"), encoding="utf-8")

    # Region classification
    regions: dict[str, list[str]] = {}
    for link in deduped:
        country = detect_country(link)
        region_key = country or "OTHER"
        regions.setdefault(region_key, []).append(link)

    # Write per-region files
    for code, links in sorted(regions.items()):
        region_raw = "\n".join(links)
        region_b64 = base64.b64encode(region_raw.encode("utf-8")).decode("utf-8")
        region_dir = PUBLIC / "regions"
        region_dir.mkdir(parents=True, exist_ok=True)
        (region_dir / f"sub_{code}.txt").write_text(region_b64, encoding="utf-8")
        (region_dir / f"sub_{code}_raw.txt").write_text(region_raw, encoding="utf-8")

    # Write regions index
    regions_index = {
        "updated": "",
        "total_nodes": len(deduped),
        "v2ray_nodes": len(v2ray_links),
        "hysteria_nodes": len(hy2_links),
        "regions": {
            code: {
                "name": COUNTRY_NAMES.get(code, "其他"),
                "emoji": EMOJI_FLAGS.get(code, "🌐"),
                "count": len(links),
            }
            for code, links in sorted(regions.items(), key=lambda x: -len(x[1]))
        },
    }
    from datetime import datetime, timezone
    regions_index["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT_REGIONS_FILE.write_text(json.dumps(regions_index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"total={len(all_links)} deduped={len(deduped)} v2ray={len(v2ray_links)} hy2={len(hy2_links)} regions={len(regions)}")


if __name__ == "__main__":
    main()
