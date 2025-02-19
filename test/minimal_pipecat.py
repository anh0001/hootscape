import os
from dotenv import load_dotenv
import asyncio
import aiohttp
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.transports.local.audio import LocalAudioTransport
from pipecat.transports.base_transport import TransportParams

# Load variables from .env file into the environment
load_dotenv()

# Retrieve the API key and voice ID from environment variables
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")

async def main():
    async with aiohttp.ClientSession() as session:
        transport = LocalAudioTransport(
            TransportParams(audio_out_enabled=True)
        )
        tts = ElevenLabsTTSService(
            aiohttp_session=session,
            api_key=elevenlabs_api_key,
            voice_id=elevenlabs_voice_id
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
