"""Generate Clash YAML and Sing-Box JSON subscription files from raw proxy links.

Reads public/sub_v2ray_raw.txt and public/sub_hysteria_raw.txt, parses each
proxy link, and converts to Clash Meta YAML and Sing-Box JSON formats.
"""

import base64
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
V2RAY_RAW = PUBLIC / "sub_v2ray_raw.txt"
HY2_RAW = PUBLIC / "sub_hysteria_raw.txt"
ALL_RAW = PUBLIC / "sub_raw.txt"

OUT_CLASH = PUBLIC / "sub_clash.yaml"
OUT_SINGBOX = PUBLIC / "sub_singbox.json"


def decode_vmess(link: str) -> dict | None:
    """Decode vmess://base64json link."""
    try:
        b64 = link[len("vmess://"):]
        raw = base64.b64decode(b64 + "==").decode("utf-8")
        cfg = json.loads(raw)
        return {
            "type": "vmess",
            "name": cfg.get("ps", "node"),
            "server": cfg.get("add", ""),
            "port": int(cfg.get("port", 443)),
            "uuid": cfg.get("id", ""),
            "alterId": int(cfg.get("aid", 0)),
            "cipher": cfg.get("scy", "auto"),
            "network": cfg.get("net", "tcp"),
            "ws-opts": {
                "path": cfg.get("path", "/"),
                "headers": {"Host": cfg.get("host", "")},
            } if cfg.get("net") == "ws" else {},
            "tls": cfg.get("tls", "") == "tls",
            "servername": cfg.get("sni", ""),
        }
    except Exception:
        return None


def parse_share_link(link: str) -> dict | None:
    """Parse a share link (vless://, trojan://, ss://, hysteria2://) into structured config."""
    if not link or "://" not in link:
        return None

    proto, rest = link.split("://", 1)

    if proto == "vmess":
        return decode_vmess(link)

    if proto in ("ss", "ssr"):
        return parse_ss_link(link, proto)

    # vless://uuid@host:port?params#name
    # trojan://password@host:port?params#name
    # hysteria2://password@host:port?params#name
    name = ""
    if "#" in rest:
        rest, name = rest.rsplit("#", 1)
        name = urllib.parse.unquote(name)

    m = re.match(r"^([^@]+)@([\w.-]+|\[[\w:]+\]):(\d+)/?(?:\?(.*))?$", rest)
    if not m:
        return None

    auth, host, port_str, query_str = m.group(1), m.group(2), m.group(3), m.group(4) or ""
    try:
        port = int(port_str)
    except ValueError:
        return None

    params = dict(urllib.parse.parse_qsl(query_str))

    node = {
        "type": proto,
        "name": name or f"{host}:{port}",
        "server": host.strip("[]"),
        "port": port,
    }

    if proto == "vless":
        node["uuid"] = auth
        node["flow"] = params.get("flow", "")
        tls = params.get("security", "none")
        node["tls"] = tls != "none"
        if tls != "none":
            node["servername"] = params.get("sni", host)
        node["network"] = params.get("type", "tcp")
        if node["network"] == "ws":
            node["ws-opts"] = {
                "path": params.get("path", "/"),
                "headers": {"Host": params.get("host", host)},
            }
        node["alpn"] = [params.get("alpn", "h2")] if params.get("alpn") else []

    elif proto == "trojan":
        node["password"] = auth
        node["tls"] = True
        node["servername"] = params.get("sni", host)
        node["network"] = params.get("type", "tcp")
        if node["network"] == "ws":
            node["ws-opts"] = {
                "path": params.get("path", "/"),
                "headers": {"Host": params.get("host", host)},
            }

    elif proto in ("hysteria2", "hy2", "hysteria"):
        node["password"] = auth
        node["tls"] = True
        node["servername"] = params.get("sni", host)
        node["network"] = "udp"
        node["up"] = params.get("up", "50")
        node["down"] = params.get("down", "100")
        if "obfs" in params:
            node["obfs"] = params["obfs"]
            node["obfs-password"] = params.get("obfs-password", "")

    elif proto == "ss":
        node = parse_ss_link(link, "ss")
        return node

    return node


def parse_ss_link(link: str, proto: str) -> dict | None:
    """Parse shadowsocks link."""
    rest = link.split("://", 1)[1]
    name = ""
    if "#" in rest:
        rest, name = rest.rsplit("#", 1)
        name = urllib.parse.unquote(name)

    # ss://base64(method:password)@host:port
    m = re.match(r"^([^@]+)@([\w.-]+):(\d+)/?(?:\?(.*))?$", rest)
    if not m:
        return None

    auth_b64, host, port_str, query_str = m.group(1), m.group(2), m.group(3), m.group(4) or ""
    try:
        auth = base64.b64decode(auth_b64 + "==").decode("utf-8")
        if ":" in auth:
            method, password = auth.split(":", 1)
        else:
            method, password = "aes-256-gcm", auth
    except Exception:
        method, password = "aes-256-gcm", auth_b64

    return {
        "type": "ss",
        "name": name or f"{host}:{port_str}",
        "server": host,
        "port": int(port_str),
        "cipher": method,
        "password": password,
    }


def to_clash_proxy(node: dict) -> dict:
    """Convert parsed node to Clash proxy dictionary."""
    proxy = {"name": node["name"], "type": node["type"], "server": node["server"], "port": node["port"]}

    if node["type"] == "vmess":
        proxy["uuid"] = node.get("uuid", "")
        proxy["alterId"] = node.get("alterId", 0)
        proxy["cipher"] = node.get("cipher", "auto")
        if node.get("network") == "ws" and node.get("ws-opts"):
            proxy["network"] = "ws"
            proxy["ws-opts"] = node["ws-opts"]
        if node.get("tls"):
            proxy["tls"] = True
            proxy["servername"] = node.get("servername", node["server"])
        proxy["udp"] = True

    elif node["type"] == "vless":
        proxy["uuid"] = node.get("uuid", "")
        proxy["flow"] = node.get("flow", "")
        if node.get("network") == "ws" and node.get("ws-opts"):
            proxy["network"] = "ws"
            proxy["ws-opts"] = node["ws-opts"]
        if node.get("tls"):
            proxy["tls"] = True
            proxy["servername"] = node.get("servername", node["server"])
            if node.get("alpn"):
                proxy["alpn"] = node["alpn"]
        proxy["udp"] = True

    elif node["type"] == "trojan":
        proxy["password"] = node.get("password", "")
        if node.get("network") == "ws" and node.get("ws-opts"):
            proxy["network"] = "ws"
            proxy["ws-opts"] = node["ws-opts"]
        proxy["tls"] = True
        proxy["servername"] = node.get("servername", node["server"])
        proxy["udp"] = True

    elif node["type"] in ("hysteria2", "hy2", "hysteria"):
        proxy["type"] = "hysteria2"
        proxy["password"] = node.get("password", "")
        proxy["sni"] = node.get("servername", node["server"])
        proxy["up"] = node.get("up", "50")
        proxy["down"] = node.get("down", "100")
        if node.get("obfs"):
            proxy["obfs"] = node["obfs"]
            proxy["obfs-password"] = node.get("obfs-password", "")

    elif node["type"] == "ss":
        proxy["cipher"] = node.get("cipher", "aes-256-gcm")
        proxy["password"] = node.get("password", "")
        proxy["udp"] = True

    return proxy


def to_singbox_outbound(node: dict) -> dict:
    """Convert parsed node to Sing-Box outbound dictionary."""
    tag = node["name"]
    outbound = {"tag": tag, "server": node["server"], "server_port": node["port"]}

    if node["type"] == "vmess":
        outbound["type"] = "vmess"
        outbound["uuid"] = node.get("uuid", "")
        outbound["alter_id"] = node.get("alterId", 0)
        outbound["security"] = node.get("cipher", "auto")
        if node.get("network") == "ws":
            outbound["transport"] = {
                "type": "ws",
                "path": node.get("ws-opts", {}).get("path", "/"),
                "headers": node.get("ws-opts", {}).get("headers", {}),
            }
        if node.get("tls"):
            outbound["tls"] = {"enabled": True, "server_name": node.get("servername", node["server"])}

    elif node["type"] == "vless":
        outbound["type"] = "vless"
        outbound["uuid"] = node.get("uuid", "")
        outbound["flow"] = node.get("flow", "")
        if node.get("network") == "ws":
            outbound["transport"] = {
                "type": "ws",
                "path": node.get("ws-opts", {}).get("path", "/"),
                "headers": node.get("ws-opts", {}).get("headers", {}),
            }
        if node.get("tls"):
            outbound["tls"] = {"enabled": True, "server_name": node.get("servername", node["server"])}
            if node.get("alpn"):
                outbound["tls"]["alpn"] = node["alpn"]

    elif node["type"] == "trojan":
        outbound["type"] = "trojan"
        outbound["password"] = node.get("password", "")
        if node.get("network") == "ws":
            outbound["transport"] = {
                "type": "ws",
                "path": node.get("ws-opts", {}).get("path", "/"),
                "headers": node.get("ws-opts", {}).get("headers", {}),
            }
        outbound["tls"] = {"enabled": True, "server_name": node.get("servername", node["server"])}

    elif node["type"] in ("hysteria2", "hy2", "hysteria"):
        outbound["type"] = "hysteria2"
        outbound["password"] = node.get("password", "")
        outbound["tls"] = {"enabled": True, "server_name": node.get("servername", node["server"])}
        outbound["up_mbps"] = int(node.get("up", 50))
        outbound["down_mbps"] = int(node.get("down", 100))
        if node.get("obfs"):
            outbound["obfs"] = {"type": node["obfs"], "password": node.get("obfs-password", "")}

    elif node["type"] == "ss":
        outbound["type"] = "shadowsocks"
        outbound["method"] = node.get("cipher", "aes-256-gcm")
        outbound["password"] = node.get("password", "")

    return outbound


def main() -> None:
    # Read all raw links
    links = []
    for f in (ALL_RAW, V2RAY_RAW, HY2_RAW):
        if f.exists():
            links.extend(l for l in f.read_text(encoding="utf-8").splitlines() if l.strip())

    links = list(dict.fromkeys(links))  # deduplicate, preserve order
    print(f"loaded {len(links)} links")

    # Parse
    nodes = []
    for link in links:
        node = parse_share_link(link)
        if node:
            nodes.append(node)

    print(f"parsed {len(nodes)} nodes")

    # Generate Clash YAML
    clash_proxies = [to_clash_proxy(n) for n in nodes]
    clash_yaml_lines = [
        "# Clash Meta 订阅配置",
        f"# 更新时间: {__import__('datetime').datetime.now().isoformat()}",
        f"# 节点数量: {len(clash_proxies)}",
        "",
        "proxies:",
    ]
    for p in clash_proxies:
        clash_yaml_lines.append(f"  - {json.dumps(p, ensure_ascii=False)}")
    clash_yaml = "\n".join(clash_yaml_lines)
    OUT_CLASH.write_text(clash_yaml, encoding="utf-8")
    print(f"clash proxies: {len(clash_proxies)}")

    # Generate Sing-Box JSON
    singbox_outbounds = [to_singbox_outbound(n) for n in nodes]
    singbox_config = {
        "outbounds": singbox_outbounds,
        "updated": __import__('datetime').datetime.now().isoformat(),
        "count": len(singbox_outbounds),
    }
    OUT_SINGBOX.write_text(json.dumps(singbox_config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"singbox outbounds: {len(singbox_outbounds)}")


if __name__ == "__main__":
    main()
