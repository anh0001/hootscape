import os
import asyncio
import signal
from dotenv import load_dotenv
from aiohttp import web, ClientSession
from core.event_bus import EventBus
from api.owl_api_controller import handle_owl_command
from robot.owl_controller import OwlController
from config.settings import settings
from audio.tts_service import TTSService

async def process_text(text: str, tts_service: TTSService):
    """
    Asynchronous wrapper for playing text.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, tts_service.play_text, text)

async def start_http_server(event_bus, owl):
    # Setup aiohttp app with the event bus in app context
    app = web.Application()
    app["event_bus"] = event_bus
    app["owl"] = owl  # add the owl to the app context
    app.router.add_post('/owl/command', handle_owl_command)  # new unified endpoint
    
    # Use AppRunner and TCPSite for non-blocking startup
    runner = web.AppRunner(app)
    await runner.setup()
    # Use settings for host and port
    site = web.TCPSite(runner, settings.http_server_host, settings.http_server_port)
    await site.start()
    # Keep server running
    while True:
        await asyncio.sleep(3600)

# Update shutdown() to remove loop.stop() and use shutdown_event
async def shutdown(tasks, session, shutdown_event):
    print("Initiating graceful shutdown...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await session.close()  # cleanup network session if needed
    shutdown_event.set()  # signal that shutdown is complete

async def main():
    load_dotenv()
    event_bus = EventBus()
    tts_service = TTSService()
    
    async with ClientSession() as session:
        # Subscribe process_text with the TTS service
        event_bus.subscribe(
            "text_received", 
            lambda text: process_text(text, tts_service)
        )
        
        # Initialize the OwlController
        owl = OwlController(
            port=settings.robot_port,
            baudrate=settings.robot_baudrate,
            timeout=settings.robot_timeout
        )
        
        http_task = asyncio.create_task(start_http_server(event_bus, owl))
        tasks = [http_task]
        
        shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, 
                lambda: asyncio.create_task(shutdown(tasks, session, shutdown_event))
            )
        
        try:
            await shutdown_event.wait()
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main())