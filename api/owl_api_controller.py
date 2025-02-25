from aiohttp import web
import asyncio
from robot.owl_controller import OwlController  # use the existing class

async def handle_owl_command(request):
    data = await request.json()
    # Process speech command if provided.
    if "speech" in data:
        speech = data["speech"]
        text = speech.get("text", "")
        if text:
            # Publish text for TTS via event bus.
            await request.app["event_bus"].publish("text_received", text)
    # Process movement command if provided.
    if "movement" in data:
        movement = data["movement"]
        move_type = movement.get("type")
        # Retrieve the owl instance from app context.
        owl: OwlController = request.app.get("owl")
        if not owl:
            return web.Response(text="Owl not initialized", status=500)
        movement_map = {
            1: owl.tilt_front,
            2: owl.tilt_back,
            3: owl.rotate_right,
            4: owl.rotate_left,
            5: owl.tilt_right,
            6: owl.tilt_left,
        }
        move_func = movement_map.get(move_type)
        if move_func:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, move_func)
        else:
            return web.Response(text="Invalid movement type", status=400)
    return web.json_response({"status": "command received"})
