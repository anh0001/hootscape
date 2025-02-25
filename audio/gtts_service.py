from io import BytesIO
from gtts import gTTS
import pydub
from pipecat.frames.frames import TextFrame, AudioFrame
from pipecat.services.base import TTSServiceBase
from pydantic import BaseModel
from enum import Enum

class Language(str, Enum):
    EN = 'en'
    # Add other languages as needed

class GttsTTSService(TTSServiceBase):
    class InputParams(BaseModel):
        language: Language = Language.EN
        sample_rate: int = 24000

    def __init__(self, params: InputParams = InputParams()):
        self.params = params

    def synthesize(self, text: str) -> bytes:
        tts = gTTS(text=text, lang=self.params.language)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        
        # Convert MP3 to WAV with desired sample rate
        audio_segment = pydub.AudioSegment.from_file(fp, format="mp3")
        audio_segment = audio_segment.set_frame_rate(self.params.sample_rate)
        
        wav_fp = BytesIO()
        audio_segment.export(wav_fp, format="wav")
        wav_fp.seek(0)
        return wav_fp.read()

    async def __call__(self, frame: TextFrame) -> AudioFrame:
        text = frame.text
        audio_data = self.synthesize(text)
        return AudioFrame(audio_data)
