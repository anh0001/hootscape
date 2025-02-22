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
from pipecat.services.elevenlabs import ElevenLabsTTSService, Language
from pipecat.transports.local.audio import LocalAudioTransport
from pipecat.transports.base_transport import TransportParams as BaseTransportParams
from pydantic import Field
from api.text_receiver import handle_text
from typing import Optional
from robot.owl_controller import OwlController  # new import

# Define a custom TransportParams model including output_device_index.
class CustomTransportParams(BaseTransportParams):
    output_device_index: Optional[int] = Field(default=None)

# Load environment variables
load_dotenv()

async def start_http_server(event_bus):
    # Setup aiohttp app with the event bus in app context
    app = web.Application()
    app["event_bus"] = event_bus
    app.router.add_post('/text', handle_text)
    
    # Use AppRunner and TCPSite for non-blocking startup
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 9123)
    await site.start()
    # Keep server running
    while True:
        await asyncio.sleep(3600)

# New async function to poll the movement config and drive the owl controller.
async def poll_owl_movement(session, owl: OwlController):
    loop = asyncio.get_running_loop()
    movement_map = {
        "1": owl.nodding,
        "2": owl.rotating,
        "3": owl.upright_posture,
        "4": owl.backward_posture,
        "5": owl.tilting,
    }
    while True:
        try:
            url = "http://54.250.108.126/getConfig.php?configKey=hootscape_movement_value"
            async with session.get(url) as resp:
                data = await resp.json()
            if data.get("result") == 1:
                movement_value = data.get("value")
                move_func = movement_map.get(movement_value)
                if move_func:
                    await loop.run_in_executor(None, move_func)
                    set_url = f"http://54.250.108.126/setConfig.php?configKey=hootscape_movement_value&configValue=0"
                    async with session.get(set_url) as set_resp:
                        await set_resp.json()
            else:
                print(f"[WARN] Unexpected result from getConfig: {data}")
        except Exception as e:
            print(f"[ERROR] Failed to poll owl movement: {e}")
        await asyncio.sleep(5)

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
        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        device_index_env = os.getenv("AUDIO_DEVICE_INDEX")
        audio_device_index = int(device_index_env) if device_index_env else None

        # Initialize TTS Service and Audio Transport using custom transport params.
        transport_params = CustomTransportParams(
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            output_device_index=audio_device_index
        )
        transport = LocalAudioTransport(transport_params)
        tts = ElevenLabsTTSService(
            aiohttp_session=session,
            api_key=elevenlabs_api_key,
            voice_id=elevenlabs_voice_id,
            sample_rate=24000,
            params=ElevenLabsTTSService.InputParams(
                language=Language.EN,
                stability=0.7,
                similarity_boost=0.8,
                style=0.5,
                use_speaker_boost=True
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

        # Instantiate the OwlController (ensure port matches your setup)
        owl = OwlController(port='/dev/tty.usbserial-AB0MHXVL')

        # Start the HTTP text receiver server, pipeline runner, and owl movement polling concurrently
        http_task = asyncio.create_task(start_http_server(event_bus))
        pipeline_task = asyncio.create_task(runner.run(task))
        poll_task = asyncio.create_task(poll_owl_movement(session, owl))
        tasks = [http_task, pipeline_task, poll_task]

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