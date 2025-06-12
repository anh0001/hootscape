from gtts import gTTS
from io import BytesIO
import pygame
import threading
from typing import Callable, Optional

class TTSService:
    def __init__(self):
        # Initialize pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._lock = threading.Lock()

    def play_text(
        self,
        text: str,
        lang: str = "en",
        on_start: Optional[Callable[[], None]] = None,
        on_end: Optional[Callable[[], None]] = None,
    ):
        """Convert text to speech and play it using pygame mixer.

        Parameters
        ----------
        text:
            The text to speak.
        lang:
            Language code for the speech.
        on_start:
            Optional callable invoked immediately before playback starts.
        on_end:
            Optional callable invoked once playback has finished.
        """

        with self._lock:
            try:
                if callable(on_start):
                    on_start()

                # Convert text to speech
                tts = gTTS(text=text, lang=lang)
                audio_fp = BytesIO()
                tts.write_to_fp(audio_fp)
                audio_fp.seek(0)

                # Load and play the audio
                pygame.mixer.music.load(audio_fp)
                pygame.mixer.music.play()

                # Wait for playback to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)

            except Exception as e:
                print(f"[ERROR] TTS playback failed: {e}")
            finally:
                if callable(on_end):
                    on_end()

