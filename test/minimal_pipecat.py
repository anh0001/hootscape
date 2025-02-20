import os
from dotenv import load_dotenv
import asyncio
import aiohttp
import pyaudio  # new import for device enumeration
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.elevenlabs import ElevenLabsTTSService, Language
from pipecat.transports.local.audio import LocalAudioTransport
# Changed: Import base model and add new field support
from pipecat.transports.base_transport import TransportParams as BaseTransportParams
from pydantic import Field
from typing import Optional

# Create a custom TransportParams model that includes output_device_index.
class CustomTransportParams(BaseTransportParams):
    output_device_index: Optional[int] = Field(default=None)

# Load variables from .env file into the environment
load_dotenv()

# Retrieve the API key and voice ID from environment variables
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
# Retrieve audio device index from env (optional)
device_index_env = os.getenv("AUDIO_DEVICE_INDEX")
audio_device_index = int(device_index_env) if device_index_env else None

async def main():
    async with aiohttp.ClientSession() as session:
        # Changed: Use the custom transport params with output_device_index.
        transport_params = CustomTransportParams(
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            output_device_index=None
        )
        transport = LocalAudioTransport(transport_params)
        
        # Changed: Instantiate ElevenLabsTTSService with custom parameters
        tts = ElevenLabsTTSService(
            aiohttp_session=session,
            api_key=elevenlabs_api_key,
            voice_id=elevenlabs_voice_id,
            sample_rate=24000,  # Set desired output sample rate (Hz)
            params=ElevenLabsTTSService.InputParams(
                language=Language.EN,        # Specify language
                stability=0.7,               # Voice stability control
                similarity_boost=0.8,        # Target voice similarity boost
                style=0.5,                   # Style adjustment for V2+ models
                use_speaker_boost=True       # Enable speaker boost
            )
        )
        pipeline = Pipeline([
            tts,                # TTS service converts text to audio
            transport.output()  # Audio transport plays the audio
        ])
        task = PipelineTask(pipeline)
        runner = PipelineRunner()
        
        # Queue a text frame that will be processed into speech.
        test_frame = TextFrame("Hello, Pipecat!")
        await task.queue_frame(test_frame)
        await runner.run(task)

if __name__ == "__main__":
    asyncio.run(main())
