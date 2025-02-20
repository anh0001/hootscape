import os
from dotenv import load_dotenv
import asyncio
import aiohttp
import pyaudio  # new import for device enumeration
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.elevenlabs import ElevenLabsTTSService, Language  # Changed: Added Language
from pipecat.transports.local.audio import LocalAudioTransport
from pipecat.transports.base_transport import TransportParams

# Load variables from .env file into the environment
load_dotenv()

# Retrieve the API key and voice ID from environment variables
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
# Retrieve audio device index from env (optional)
device_index_env = os.getenv("AUDIO_DEVICE_INDEX")
audio_device_index = int(device_index_env) if device_index_env else None

# If no index specified, list available output devices
if audio_device_index is None:
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get('maxOutputChannels') > 0:
            print(f"Output Device id {i} - {dev.get('name')}")
    p.terminate()

async def main():
    async with aiohttp.ClientSession() as session:
        # Build TransportParams without forcing output_device_index if not provided.
        transport_params = TransportParams(
            audio_out_enabled=True,
            audio_out_sample_rate=44100  # match TTS service sample rate
        )
        if audio_device_index is not None:
            transport_params = transport_params.copy(update={"output_device_index": audio_device_index})
        
        transport = LocalAudioTransport(transport_params)
        
        # Changed: Instantiate ElevenLabsTTSService with custom parameters
        tts = ElevenLabsTTSService(
            aiohttp_session=session,
            api_key=elevenlabs_api_key,
            voice_id=elevenlabs_voice_id,
            sample_rate=44100,  # Set desired output sample rate (Hz)
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
