import os
import asyncio
import signal
from dotenv import load_dotenv
from aiohttp import web, ClientSession
from core.event_bus import EventBus
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from audio.gtts_service import GttsTTSService, Language
from pipecat.transports.local.audio import LocalAudioTransport
from pipecat.transports.base_transport import TransportParams as BaseTransportParams
from pydantic import Field
from api.owl_api_controller import handle_owl_command  # new unified endpoint
from typing import Optional
from robot.owl_controller import OwlController  # already imported
from config.settings import settings  # new import for settings

# Define a custom TransportParams model including output_device_index.
class CustomTransportParams(BaseTransportParams):
    output_device_index: Optional[int] = Field(default=None)

# Load environment variables
load_dotenv()

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
    # Initialize event bus and create an aiohttp session
    event_bus = EventBus()
    async with ClientSession() as session:
        # Retrieve API keys and audio device index from env
        device_index_env = os.getenv("AUDIO_DEVICE_INDEX")
        audio_device_index = int(device_index_env) if device_index_env else None

        # Initialize TTS Service and Audio Transport using custom transport params.
        transport_params = CustomTransportParams(
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            output_device_index=audio_device_index
        )
        transport = LocalAudioTransport(transport_params)
        
        # Replace ElevenLabs with gTTS
        tts = GttsTTSService(
            params=GttsTTSService.InputParams(
                language=Language.EN,
                sample_rate=24000
            )
        )

        # Build the pipeline (TTS converts text to audio, transport plays audio)
        pipeline = Pipeline([
            tts,
            transport.output()
        ])
        task = PipelineTask(pipeline)
        runner = PipelineRunner()

        # Subscribe a handler to enqueue a text frame when text is received.
        async def process_text(text):
            await task.queue_frame(TextFrame(text))
        event_bus.subscribe("text_received", process_text)

        # Instantiate the OwlController using settings
        owl = OwlController(
            port=settings.robot_port,
            baudrate=settings.robot_baudrate,
            timeout=settings.robot_timeout
        )

        # Start the HTTP text receiver server and owl command server concurrently.
        http_task = asyncio.create_task(start_http_server(event_bus, owl))
        pipeline_task = asyncio.create_task(runner.run(task))
        tasks = [http_task, pipeline_task]

        shutdown_event = asyncio.Event()  # Instantiate shutdown event

        loop = asyncio.get_running_loop()
        # Update signal handlers to call the new shutdown() without stopping the loop.
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(tasks, session, shutdown_event)))

        try:
            await shutdown_event.wait()  # Wait until shutdown is triggered.
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main())