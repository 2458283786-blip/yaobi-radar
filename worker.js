export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // Direct relay to Binance
    const target = "https://fapi.binance.com" + url.pathname + url.search;
    
    try {
      const response = await fetch(target, {
        headers: { "User-Agent": "Mozilla/5.0" }
      });
      const data = await response.json();
      return Response.json(data);
    } catch (e) {
      return Response.json({ error: e.message, target: target }, { status: 502 });
    }
  }
}
