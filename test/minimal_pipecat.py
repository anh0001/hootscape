import asyncio
import aiohttp
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.transports.local.audio import LocalAudioTransport
from pipecat.transports.base_transport import TransportParams

async def main():
    async with aiohttp.ClientSession() as session:
        transport = LocalAudioTransport(
            TransportParams(audio_out_enabled=True)
        )
        tts = ElevenLabsTTSService(
            aiohttp_session=session,
            api_key="sk_c0d6a7d853bc553f0b169fc4f2ac66506865b502704fdfc7",  # Replace with your API key
            voice_id="Xb7hH8MSUJpSbSDYk0k2"            # Replace with your voice ID
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
