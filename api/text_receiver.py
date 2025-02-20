from aiohttp import web

async def handle_text(request):
    data = await request.json()
    text = data.get("text", "")
    if text:
        await request.app["event_bus"].publish("text_received", text)
    return web.Response(text="Text queued.")
