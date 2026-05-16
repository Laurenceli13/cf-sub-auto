/**
 * Cloudflare Worker: protect subscription with token and proxy to GitHub Pages.
 *
 * Set these vars in Wrangler or Dashboard:
 * - ORIGIN_BASE: e.g. https://<user>.github.io/<repo>
 * - SUB_TOKEN: strong random token
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = (env.ORIGIN_BASE || "").replace(/\/$/, "");

    if (url.pathname === "/health") {
      const upstream = origin ? `${origin}/public/sub_v2ray.txt` : "";
      let upstreamOk = false;
      let upstreamStatus = 0;
      let upstreamLength = null;
      let error = null;

      if (upstream) {
        try {
          const check = await fetch(upstream, {
            headers: { "User-Agent": "sub-gateway/1.0" },
            cf: { cacheTtl: 30, cacheEverything: false }
          });
          upstreamStatus = check.status;
          upstreamOk = check.ok;
          upstreamLength = check.headers.get("content-length");
        } catch (e) {
          error = e instanceof Error ? e.message : String(e);
        }
      }

      return new Response(
        JSON.stringify(
          {
            ok: Boolean(origin) && upstreamOk,
            service: "sub-gateway",
            time: new Date().toISOString(),
            configured: Boolean(origin) && Boolean(env.SUB_TOKEN),
            originConfigured: Boolean(origin),
            tokenConfigured: Boolean(env.SUB_TOKEN),
            upstream,
            upstreamOk,
            upstreamStatus,
            upstreamLength,
            error
          },
          null,
          2
        ),
        {
          status: upstreamOk ? 200 : 503,
          headers: {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store"
          }
        }
      );
    }

    if (url.pathname !== "/sub.txt") {
      return new Response("Not Found", { status: 404 });
    }

    const token = url.searchParams.get("token");
    if (!token || token !== env.SUB_TOKEN) {
      return new Response("Forbidden", { status: 403 });
    }

    if (!origin) {
      return new Response("Worker not configured", { status: 500 });
    }

    const upstream = `${origin}/public/sub_v2ray.txt`;
    const res = await fetch(upstream, {
      headers: {
        "User-Agent": "sub-gateway/1.0"
      },
      cf: {
        cacheTtl: 60,
        cacheEverything: true
      }
    });

    if (!res.ok) {
      return new Response(`Upstream error: ${res.status}`, { status: 502 });
    }

    return new Response(await res.text(), {
      status: 200,
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "public, max-age=60"
      }
    });
  }
};
