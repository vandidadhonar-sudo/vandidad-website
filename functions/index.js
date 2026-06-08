export async function onRequestPost(context) {
  const LAMBDA = "https://qyfm5ip2y7e2xmlakzzolzd6ai0mkkrn.lambda-url.us-east-1.on.aws";
  try {
    const body = await context.request.text();
    const resp = await fetch(LAMBDA, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body,
    });
    return new Response(resp.body, {
      status: resp.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (e) {
    return new Response(
      'data: {"type":"error","message":"خطا در اتصال"}\n\n',
      { headers: { "Content-Type": "text/event-stream" } }
    );
  }
}
