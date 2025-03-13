# main.py
import os
import asyncio
import signal
import logging
from dotenv import load_dotenv
from aiohttp import web, ClientSession
from core.event_bus import EventBus
from api.owl_api_controller import handle_owl_command
from robot.owl_controller import OwlController
from config.settings import settings
from audio.tts_service import TTSService
from voice.recognition import VoiceSystem
from voice.commands.handlers import HealthcareCommands
from audio.soundscape import SoundscapeManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("hootscape.log")
    ]
)

logger = logging.getLogger("main")

async def process_text(text: str, tts_service: TTSService):
    """
    Asynchronous wrapper for playing text.
    """
    logger.info(f"Processing text: {text}")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, tts_service.play_text, text)

async def process_owl_movements(movements: list, owl_controller: OwlController):
    """
    Process a sequence of owl movements
    """
    logger.info(f"Processing owl movements: {movements}")
    for move in movements:
        move_type = move.get("type")
        duration = move.get("duration", 1)
        
        # Map movement types to owl controller methods
        movement_map = {
            1: owl_controller.tilt_front,
            2: owl_controller.tilt_back,
            3: owl_controller.rotate_right,
            4: owl_controller.rotate_left,
            5: owl_controller.tilt_right,
            6: owl_controller.tilt_left,
        }
        
        move_func = movement_map.get(move_type)
        if move_func:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, move_func)
            await asyncio.sleep(duration)

async def start_http_server(event_bus, owl, tts_service):
    # Setup aiohttp app with the event bus and tts service in app context
    app = web.Application()
    app["event_bus"] = event_bus
    app["owl"] = owl
    app["tts_service"] = tts_service
    app.router.add_post('/owl/command', handle_owl_command)
    
    # Use AppRunner and TCPSite for non-blocking startup
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.http_server_host, settings.http_server_port)
    await site.start()
    
    logger.info(f"HTTP server started on {settings.http_server_host}:{settings.http_server_port}")
    
    # Keep server running
    while True:
        await asyncio.sleep(3600)

async def startup_sequence(owl_controller, soundscape, event_bus, tts_service):
    """
    Execute a welcoming startup sequence
    """
    # Start the forest ambience - now using the OpenAL implementation
    forest_sources = await soundscape.create_forest_ambience()
    logger.info(f"Started forest ambience with {len(forest_sources)} sound sources")
    
    # Play a mother owl sound as part of the welcome
    owl_position = [2.5, 3.0, 2.0]  # Position in the virtual room
    owl_source = await soundscape.play_mother_owl_sound(owl_position)
    
    # Make owl greet the user
    welcome_movements = [
        {"type": 3, "duration": 1},  # Turn right
        {"type": 4, "duration": 1},  # Turn left
        {"type": 1, "duration": 1},  # Tilt forward (like a bow)
    ]
    await process_owl_movements(welcome_movements, owl_controller)
    
    # Welcome message
    welcome_text = "Hello, I'm your owl companion. I'm here to help you with medication reminders, " + \
                  "health monitoring, and to keep you company. Just say 'Hey Owl' to get my attention."
    await process_text(welcome_text, tts_service)

async def shutdown(tasks, session, voice_system, soundscape, shutdown_event):
    """
    Gracefully shut down all components
    """
    logger.info("Initiating graceful shutdown...")
    
    # First stop the update thread in soundscape if it exists
    if soundscape:
        logger.info("Stopping soundscape update thread...")
        soundscape.stop_update_thread()
    
    # Explicitly stop the voice system first 
    if voice_system:
        logger.info("Stopping voice system...")
        await voice_system.stop()
    
    # Cancel all tasks and wait for them to complete
    for task in tasks:
        if not task.done():
            task.cancel()
    
    # Wait for all tasks to complete with a timeout
    try:
        await asyncio.wait(tasks, timeout=5)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled")
    
    # Clean up soundscape resources after tasks are cancelled
    if soundscape:
        logger.info("Cleaning up soundscape resources...")
        soundscape.cleanup()
    
    # Close any remaining sessions
    if session and not session.closed:
        await session.close()
    
    logger.info("Setting shutdown event")
    shutdown_event.set()
    
    # Force exit after a timeout to ensure complete shutdown
    logger.info("Setting force exit timer (3 seconds)")
    loop = asyncio.get_running_loop()
    loop.call_later(3, lambda: os._exit(0))

async def main():
    logger.info("Starting HootScape Healthcare Assistant")
    load_dotenv()
    
    # Initialize core components
    event_bus = EventBus()
    tts_service = TTSService()
    
    async with ClientSession() as session:
        # Initialize owl controller
        owl = OwlController(
            port=settings.robot_port,
            baudrate=settings.robot_baudrate,
            timeout=settings.robot_timeout
        )
        
        # Initialize soundscape manager
        soundscape = SoundscapeManager(event_bus)
        
        # Initialize voice system
        voice_system = VoiceSystem(event_bus)
        
        # Initialize healthcare command handlers
        healthcare_commands = HealthcareCommands(event_bus, owl, tts_service)
        
        # Subscribe event handlers
        event_bus.subscribe(
            "text_received", 
            lambda text: process_text(text, tts_service)
        )
        
        event_bus.subscribe(
            "owl_movements",
            lambda movements: process_owl_movements(movements, owl)
        )
        
        # Start HTTP server task
        http_task = asyncio.create_task(start_http_server(event_bus, owl, tts_service))
        
        # Start voice recognition task
        voice_task = asyncio.create_task(voice_system.start())
        
        # Start with a welcome sequence
        startup_task = asyncio.create_task(startup_sequence(owl, soundscape, event_bus, tts_service))
        
        # Collect all tasks
        tasks = [http_task, voice_task, startup_task]
        
        # Set up shutdown handling
        shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        
        def signal_handler():
            logger.info("Interrupt received, shutting down...")
            asyncio.create_task(shutdown(tasks, session, voice_system, soundscape, shutdown_event))

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
        
        try:
            logger.info("System initialized and running")
            await shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        
        logger.info("HootScape shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())