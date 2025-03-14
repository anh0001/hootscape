from pydantic_settings import BaseSettings
from pydantic import Field
from enum import Enum

class SpeechRecognitionProvider(str, Enum):
    """Speech recognition provider options"""
    WHISPER = "whisper"  # Use local Whisper model (default)
    OPENAI = "openai"    # Use OpenAI's cloud API (better accuracy)

class Settings(BaseSettings):
    # HTTP server settings
    http_server_host: str = Field(default="0.0.0.0", env="HTTP_SERVER_HOST")
    http_server_port: int = Field(default=9123, env="HTTP_SERVER_PORT")

    # Robot serial communication settings
    robot_port: str = Field(default="/dev/ttyUSB0", env="ROBOT_PORT")
    robot_baudrate: int = Field(default=57600, env="ROBOT_BAUDRATE")
    robot_timeout: float = Field(default=1.0, env="ROBOT_TIMEOUT")

    # Audio settings
    audio_sample_rate: int = Field(default=44100, env="AUDIO_SAMPLE_RATE")
    audio_channels: int = Field(default=2, env="AUDIO_CHANNELS")
    audio_buffer_size: int = Field(default=1024, env="AUDIO_BUFFER_SIZE")

    # Speech Recognition settings
    # To change the provider, modify this value directly or set SPEECH_RECOGNITION_PROVIDER env var
    speech_recognition_provider: SpeechRecognitionProvider = Field(
        default=SpeechRecognitionProvider.OPENAI, 
        env="SPEECH_RECOGNITION_PROVIDER",
        description="Speech recognition provider (whisper or openai)"
    )

    # OpenAI API settings - keep API key in .env file, but model can be modified here
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="whisper-1", env="OPENAI_MODEL")

    # ElevenLabs TTS settings
    elevenlabs_api_key: str = Field(default="", env="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = Field(default="", env="ELEVENLABS_VOICE_ID")
    tts_sample_rate: int = Field(default=24000, env="TTS_SAMPLE_RATE")

    # New settings for synchronized movement
    enable_synchronized_movements: bool = Field(default=True, env="ENABLE_SYNCHRONIZED_MOVEMENTS")
    movement_analysis_model: str = Field(default="gpt-3.5-turbo", env="MOVEMENT_ANALYSIS_MODEL")

    class Config:
        env_file = ".env"  # auto-load environment variables from .env
        extra = "allow"  # allow extra fields in .env file

# Instantiate settings for global use.
settings = Settings()