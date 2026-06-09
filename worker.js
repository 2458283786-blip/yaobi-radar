export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = "https://fapi.binance.com" + url.pathname + url.search;
    
    try {
      const response = await fetch(target, {
        headers: { "User-Agent": "Mozilla/5.0" }
      });
      const text = await response.text();
      return new Response(text, {
        status: response.status,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "public, max-age=30"
        }
      });
    } catch (e) {
      return Response.json({ error: e.message }, { status: 502 });
    }
  }
}
