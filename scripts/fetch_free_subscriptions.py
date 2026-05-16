import base64
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "public" / "sub.txt"
OUT_RAW_FILE = ROOT / "public" / "sub_raw.txt"

SOURCES = [
    "https://raw.githubusercontent.com/awesome-vpn/awesome-vpn/master/all",
    "https://raw.githubusercontent.com/shaoyouvip/free/refs/heads/main/base64.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
]

LINK_RE = re.compile(r"(?im)^(?:vmess|vless|trojan|ss|ssr|hy2|hysteria2|hysteria)://\S+$")


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


def main() -> None:
    all_links: list[str] = []
    for url in SOURCES:
        content = fetch_text(url)
        decoded = maybe_base64_decode(content)
        links = extract_links(decoded)
        all_links.extend(links)
        print(f"source={url} links={len(links)}")

    deduped = sorted(set(all_links))
    raw = "\n".join(deduped)
    b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")

    OUT_RAW_FILE.write_text(raw, encoding="utf-8")
    OUT_FILE.write_text(b64, encoding="utf-8")
    print(f"total={len(all_links)} deduped={len(deduped)}")


if __name__ == "__main__":
    main()
