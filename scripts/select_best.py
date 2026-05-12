import json
import socket
import ssl
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODES_FILE = ROOT / "nodes" / "nodes.json"
OUT_FILE = ROOT / "nodes" / "selected.json"

def tcp_latency(host: str, port: int, timeout: float = 2.5):
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return None

def tls_check(host: str, port: int, sni: str, timeout: float = 3.0):
    ctx = ssl.create_default_context()
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni) as ssock:
                ssock.do_handshake()
                _ = ssock.getpeercert()
        return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return None

def score_node(node: dict):
    host = node["address"]
    port = int(node["port"])
    sni = node.get("sni") or node.get("host") or host

    tcp_ms = tcp_latency(host, port)
    tls_ms = tls_check(host, port, sni) if node.get("tls", True) else 0.0

    alive = tcp_ms is not None and (tls_ms is not None)
    if not alive:
        return {**node, "alive": False, "score": -1, "tcp_ms": tcp_ms, "tls_ms": tls_ms}

    # 越低越好，简单线性打分
    total_ms = float(tcp_ms) + float(tls_ms)
    score = max(0.0, 1000.0 - total_ms)
    return {**node, "alive": True, "score": round(score, 2), "tcp_ms": round(tcp_ms, 2), "tls_ms": round(tls_ms, 2)}

def main():
    nodes = json.loads(NODES_FILE.read_text(encoding="utf-8-sig"))
    scored = [score_node(n) for n in nodes]
    scored.sort(key=lambda x: x["score"], reverse=True)

    top_n = 3
    selected = [n for n in scored if n["alive"]][:top_n]

    OUT_FILE.write_text(json.dumps({"selected": selected, "all": scored}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"scored={len(scored)} selected={len(selected)}")

if __name__ == "__main__":
    main()
