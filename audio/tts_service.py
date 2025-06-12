from gtts import gTTS
from gtts.tts import gTTSError
from io import BytesIO
import pygame
import threading
from typing import Callable, Optional
import logging
import requests
from config.settings import settings

class TTSService:
    def __init__(self):
        # Initialize pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self._timeout = getattr(settings, "tts_request_timeout", 10)

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
                tts = gTTS(text=text, lang=lang, timeout=self._timeout)
                audio_fp = BytesIO()

                try:
                    tts.write_to_fp(audio_fp)
                except (gTTSError, requests.RequestException) as e:
                    self.logger.error(f"TTS generation failed: {e}")
                    if callable(on_end):
                        on_end()
                    return

                audio_fp.seek(0)

                # Load and play the audio
                pygame.mixer.music.load(audio_fp)
                pygame.mixer.music.play()

                # Wait for playback to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)

            except Exception as e:
                self.logger.error(f"TTS playback failed: {e}")
            finally:
                if callable(on_end):
                    on_end()

