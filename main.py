import os
import asyncio
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
from api.text_receiver import handle_text  # new import
from typing import Optional  # added import

# Define a custom TransportParams model including output_device_index.
class CustomTransportParams(BaseTransportParams):
    output_device_index: Optional[int] = Field(default=None)  # updated type annotation

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
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    # Keep server running
    while True:
        await asyncio.sleep(3600)

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

        # Start the HTTP text receiver server concurrently
        asyncio.create_task(start_http_server(event_bus))
        # Run the pipeline runner concurrently.
        asyncio.create_task(runner.run(task))
        
        try:
            while True:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            # Cleanup if necessary
            pass

if __name__ == "__main__":
    asyncio.run(main())