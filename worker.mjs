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
    if (url.pathname !== "/sub.txt") {
      return new Response("Not Found", { status: 404 });
    }

    const token = url.searchParams.get("token");
    if (!token || token !== env.SUB_TOKEN) {
      return new Response("Forbidden", { status: 403 });
    }

    const origin = (env.ORIGIN_BASE || "").replace(/\/$/, "");
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
