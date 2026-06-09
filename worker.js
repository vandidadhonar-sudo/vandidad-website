export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Serve index.html for all routes
    const html = await env.ASSETS.fetch(new Request(new URL('/index.html', request.url)));
    return new Response(html.body, {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' }
    });
  }
}