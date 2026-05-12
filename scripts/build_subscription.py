import base64
import json
import os
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELECTED_FILE = ROOT / "nodes" / "selected.json"
OUT_FILE = ROOT / "public" / "sub.txt"

def to_vless_link(node: dict) -> str:
    uuid = node["uuid"]
    address = node["address"]
    port = int(node["port"])
    path = node.get("path", "/")
    host = node.get("host", "")
    sni = node.get("sni", host)
    fp = node.get("fingerprint", "chrome")
    name = urllib.parse.quote(node.get("name", "node"))

    q = {
        "type": "ws",
        "security": "tls",
        "path": path,
        "host": host,
        "sni": sni,
        "fp": fp,
        "encryption": "none"
    }
    query = urllib.parse.urlencode(q, safe="/")
    return f"vless://{uuid}@{address}:{port}?{query}#{name}"

def main():
    obj = json.loads(SELECTED_FILE.read_text(encoding="utf-8"))
    nodes = obj.get("selected", [])

    links = [to_vless_link(n) for n in nodes]
    raw = "\n".join(links)
    b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")

    token = os.getenv("SUBSCRIPTION_TOKEN", "")
    if not token:
        print("warning: SUBSCRIPTION_TOKEN is empty (URL protection won't work by nginx/pages rule)")

    OUT_FILE.write_text(b64, encoding="utf-8")
    print(f"generated_links={len(links)}")

if __name__ == "__main__":
    main()
