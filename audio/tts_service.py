from gtts import gTTS
from io import BytesIO
import pygame
import threading

class TTSService:
    def __init__(self):
        # Initialize pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._lock = threading.Lock()

    def play_text(self, text: str, lang: str = "ja"):
        """
        Convert text to speech and play it using pygame mixer.
        """
        with self._lock:
            try:
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
