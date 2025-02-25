from aiohttp import web
import asyncio
from robot.owl_controller import OwlController  # use the existing class

# New helper function to execute a sequence of movements
async def execute_movement_sequence(owl, movements):
    loop = asyncio.get_running_loop()
    movement_map = {
        1: owl.tilt_front,
        2: owl.tilt_back,
        3: owl.rotate_right,
        4: owl.rotate_left,
        5: owl.tilt_right,
        6: owl.tilt_left,
    }
    for move in movements:
        move_type = move.get("type")
        duration = move.get("duration", 1)
        move_func = movement_map.get(move_type)
        if move_func:
            await loop.run_in_executor(None, move_func)
            await asyncio.sleep(duration)
        else:
            print(f"Invalid movement type: {move_type}")

async def handle_owl_command(request):
    data = await request.json()
    # Process speech command if provided.
    if "speech" in data:
        speech = data["speech"]
        text = speech.get("text", "")
        if text:
            # Publish text for TTS via event bus.
            await request.app["event_bus"].publish("text_received", text)
    # Process sequence of movements if provided.
    if "movements" in data:
        movements = data["movements"]
        asyncio.create_task(execute_movement_sequence(request.app["owl"], movements))
    # Process macro command by mapping a name to a sequence.
    elif "macro" in data:
        macro = data["macro"]
        if macro == "happy":
            sequence = [
                {"type": 5, "duration": 1},
                {"type": 6, "duration": 1},
                {"type": 5, "duration": 1},
                {"type": 6, "duration": 1},
                {"type": 5, "duration": 1},
                {"type": 6, "duration": 1},
            ]
            asyncio.create_task(execute_movement_sequence(request.app["owl"], sequence))
        else:
            return web.Response(text="Unknown macro", status=400)
    # Fallback for legacy single movement (optional)
    elif "movement" in data:
        movement = data["movement"]
        move_type = movement.get("type")
        loop = asyncio.get_running_loop()
        movement_map = {
            1: request.app["owl"].tilt_front,
            2: request.app["owl"].tilt_back,
            3: request.app["owl"].rotate_right,
            4: request.app["owl"].rotate_left,
            5: request.app["owl"].tilt_right,
            6: request.app["owl"].tilt_left,
        }
        move_func = movement_map.get(move_type)
        if move_func:
            loop.run_in_executor(None, move_func)
        else:
            return web.Response(text="Invalid movement type", status=400)
    return web.json_response({"status": "command received"})
