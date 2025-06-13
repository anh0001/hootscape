# voice/recognition.py
import asyncio
import os
from typing import Callable, Dict, Any, Optional
import json
import logging
import tempfile
import io
import wave
import audioop
import time

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import TextFrame, InputAudioRawFrame, OutputAudioRawFrame
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.transports.base_transport import TransportParams
from pipecat.services.whisper import WhisperSTTService, Model
from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter
from pipecat.processors.frame_processor import FrameProcessor
from pydantic import BaseModel, ConfigDict, Field
from core.event_bus import EventBus

# Try to import OpenAI service from pipecat if available
try:
    from pipecat.services.openai import OpenAISTTService, OpenAISTTServiceParams
    HAS_PIPECAT_OPENAI = True
except (ImportError, AttributeError):
    HAS_PIPECAT_OPENAI = False

from config.settings import settings, SpeechRecognitionProvider

logger = logging.getLogger("voice_system")

# Create our own TextProcessor class based on FrameProcessor
class TextProcessor(FrameProcessor):
    """Base class for text processing tasks in the pipeline."""
    
    def __init__(self, **kwargs):
        # Initialize FrameProcessor properly
        super().__init__(**kwargs)
    
    async def process_frame(self, frame, direction):
        """Override this method in subclasses to process text frames."""
        await super().process_frame(frame, direction)
        # Process the frame here
        await self.push_frame(frame, direction)

# Simple NLP processor for healthcare commands
class HealthcareNLP(TextProcessor):
    """
    Simple NLP processor for healthcare commands optimized for elderly users.
    """
    
    class InputParams(BaseModel):
        command_handler: Optional[Callable] = Field(default=None, description="Callback for handling commands")
        event_bus: Optional[EventBus] = Field(default=None, description="Event bus for publishing messages")
        
        model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, params: InputParams = None, event_bus: Optional[EventBus] = None, **kwargs):
        """Initialize the NLP processor and ensure a command handler is set."""
        # Initialize parent properly
        super().__init__(**kwargs)

        # Create parameters if none provided
        self.nlp_params = params or self.InputParams()

        # Event bus can be provided directly or via params
        self.event_bus = event_bus or self.nlp_params.event_bus

        # Default to this class's handle_command if no handler provided
        if self.nlp_params.command_handler is None:
            self.nlp_params.command_handler = self.handle_command
        
        # Initialize MarkdownTextFilter for text preprocessing if needed
        self.text_filter = MarkdownTextFilter(
            MarkdownTextFilter.InputParams(
                enable_text_filter=True,
                filter_code=True,
                filter_tables=True
            )
        )
        
        # Add processing control to prevent overlapping
        self.last_process_time = 0
        self.processing_cooldown = 2.0  # 2 seconds between processing
    
    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        
        if not isinstance(frame, TextFrame):
            await self.push_frame(frame, direction)
            return
            
        text = frame.text.lower().strip()
        logger.info(f"Processing text: {text}")
        
        # Add cooldown to prevent rapid-fire processing
        current_time = time.time()
        if current_time - self.last_process_time < self.processing_cooldown:
            logger.debug(f"Skipping processing due to cooldown")
            await self.push_frame(frame, direction)
            return
        
        # Skip processing if empty or too short
        if not text or len(text) < 3:
            await self.push_frame(frame, direction)
            return
        
        # Filter out common transcription artifacts
        artifacts = ["thank you for watching", "thanks for watching", "thank you", "you"]
        if any(text.strip() == artifact for artifact in artifacts):
            logger.debug(f"Skipping artifact: {text}")
            await self.push_frame(frame, direction)
            return
            
        # Improved wake word detection
        wake_words = ["hey owl", "hello owl", "hi owl"]
        is_wake_word = False
        wake_word_used = ""
        
        for word in wake_words:
            if word in text:
                is_wake_word = True
                wake_word_used = word
                # Extract text after wake word
                parts = text.split(word, 1)
                if len(parts) > 1:
                    text = parts[1].strip()
                else:
                    text = ""
                break
        
        # If no wake word, skip processing
        if not is_wake_word:
            logger.debug(f"No wake word detected in: {text}")
            await self.push_frame(frame, direction)
            return
        
        logger.info(f"Wake word '{wake_word_used}' detected, processing: '{text}'")
        self.last_process_time = current_time
        
        # Better intent classification
        intent = "greeting"  # Default for wake word with no additional text
        entities = {}
        
        # If there's additional text after wake word, classify it
        if text:
            # Medication reminders
            if any(word in text for word in ["medicine", "medication", "pill", "pills", "drug", "take"]):
                intent = "medication_reminder"
                # Try to extract medication name
                for med in ["aspirin", "insulin", "blood pressure", "heart", "diabetes"]:
                    if med in text:
                        entities["medication"] = med
                        
            # Emergency help
            elif any(word in text for word in ["help", "emergency", "call", "hurt", "pain", "sick"]):
                intent = "emergency_assistance"
                if "call" in text:
                    for contact in ["doctor", "nurse", "family", "daughter", "son"]:
                        if contact in text:
                            entities["contact"] = contact
                            
            # Health check-in
            elif any(phrase in text for phrase in ["how am i", "check", "health", "feeling", "blood pressure", "temperature"]):
                intent = "health_check"
                for measure in ["blood pressure", "temperature", "heart rate", "sugar", "glucose"]:
                    if measure in text:
                        entities["measure"] = measure
                        
            # Questions
            elif any(word in text for word in ["what", "how", "when", "where", "time", "date", "weather"]):
                intent = "general_query"
                entities["query_text"] = text
                
            # Help requests
            elif any(word in text for word in ["help", "assist", "support"]):
                intent = "help_request"
                
            else:
                # Default to social interaction for other text
                intent = "social_interaction"
        
        result = {
            "intent": intent,
            "entities": entities,
            "original_text": text,
            "wake_word": wake_word_used
        }
        
        logger.info(f"Processed intent: {intent}")
        
        # If there's a command handler, call it
        if self.nlp_params.command_handler:
            try:
                await self.nlp_params.command_handler(result)
            except Exception as e:
                logger.error(f"Error in command handler: {e}")
        
        # Push the frame to the next component
        await self.push_frame(frame, direction)
    
    async def handle_command(self, command_data):
        """Handle processed voice commands with better responses"""
        logger.info(f"Command detected: {json.dumps(command_data)}")
        
        # Publish to event bus to notify other components
        await self.event_bus.publish("voice_command", command_data)
        
        # Get intent and entities
        intent = command_data["intent"]
        entities = command_data.get("entities", {})
        wake_word = command_data.get("wake_word", "hey owl")
        original_text = command_data.get("original_text", "")
        
        # Better response generation
        response_text = ""
        
        if intent == "greeting":
            responses = [
                "Hello! I'm here and ready to help you. What do you need?",
                "Hi there! How can I assist you today?",
                "Hello! I'm listening. What would you like to do?",
                "Hi! I'm your owl companion. How can I help?"
            ]
            import random
            response_text = random.choice(responses)
            
        elif intent == "help_request":
            response_text = ("I can help you with several things: medication reminders, health monitoring, "
                           "emergency assistance, or just keep you company. What would you like to do?")
            
        elif intent == "medication_reminder":
            medication = entities.get("medication", "your medication")
            response_text = f"Let me help you with {medication}. Is it time to take it, or would you like me to set a reminder?"
            
        elif intent == "emergency_assistance":
            contact = entities.get("contact", "emergency services")
            response_text = f"I understand you need help. I can contact {contact} for you. Should I do that now?"
            
        elif intent == "health_check":
            measure = entities.get("measure", "your health")
            response_text = f"Let's check {measure}. Do you have the equipment ready, or would you like instructions?"
            
        elif intent == "social_interaction":
            responses = [
                "I'm happy to chat with you! How has your day been?",
                "I'm here to keep you company. What's on your mind?",
                "I'd love to talk with you. What would you like to discuss?",
            ]
            import random
            response_text = random.choice(responses)
            
        elif intent == "general_query":
            query = entities.get("query_text", original_text)
            if "time" in query:
                import datetime
                current_time = datetime.datetime.now().strftime("%I:%M %p")
                response_text = f"The current time is {current_time}."
            elif "date" in query or "day" in query:
                import datetime
                current_date = datetime.datetime.now().strftime("%A, %B %d")
                response_text = f"Today is {current_date}."
            else:
                response_text = f"You asked about: {query}. Let me see if I can help with that."
        else:
            response_text = "I heard you, but I'm not sure what you'd like me to do. Could you try asking in a different way?"
        
        # Based on settings, choose synchronized or regular TTS
        if response_text:
            if (hasattr(settings, 'enable_synchronized_movements') and 
                settings.enable_synchronized_movements and 
                settings.openai_api_key):
                await self.send_synchronized_speech(response_text)
            else:
                # Use the original event bus approach for TTS
                await self.event_bus.publish("text_received", response_text)
    
    def generate_simple_response(self, intent, entities, original_text):
        """Generate a simple response when OpenAI isn't available"""
        if intent == "greeting":
            return "Hello! How can I help you today?"
        elif intent == "help_request":
            return "I'm here to help. You can ask me about medications, health checks, or emergency assistance."
        else:
            return "I'm listening. What would you like me to do?"
    
    async def send_synchronized_speech(self, text):
        """Send text to the synchronized speech API endpoint"""
        try:
            import aiohttp
            
            endpoint = "http://localhost:9123/owl/synchronized_speech"  # Adjust port if needed
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json={"text": text}) as response:
                    if response.status != 200:
                        # Fall back to regular TTS if API call fails
                        logger.warning(f"Synchronized speech API call failed, falling back to regular TTS")
                        await self.event_bus.publish("text_received", text)
        except Exception as e:
            logger.error(f"Error sending to synchronized speech endpoint: {e}")
            # Fall back to regular TTS
            await self.event_bus.publish("text_received", text)

class OpenAIAudioProcessor(FrameProcessor):
    """
    Processor that buffers audio frames and sends them to OpenAI's speech recognition API.
    This provides better speech recognition for elderly users.
    """
    
    class InputParams(BaseModel):
        api_key: str = Field(default="", description="OpenAI API key")
        model: str = Field(default="whisper-1", description="OpenAI model to use")
        buffer_duration_ms: int = Field(default=4000, description="Duration of audio to buffer before processing (ms)")
        enable_vad: bool = Field(default=True, description="Enable VAD based buffering")
        vad_silence_ms: int = Field(default=1000, description="Required silence duration to trigger processing (ms)")
        sample_rate: int = Field(default=16000, description="Sample rate of the audio")
        language: str = Field(default="en", description="Language code")
        
    def __init__(self, params: InputParams = None, **kwargs):
        super().__init__(**kwargs)
        self.params = params or self.InputParams()
        self.audio_buffer = b""
        self.last_process_time = 0
        self.is_processing = False
        self.silence_start = None
        # Add minimum buffer size to prevent short audio errors
        self.min_buffer_size = self.params.sample_rate * 2 * 1  # 1 second minimum
        
    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        
        # Only process InputAudioRawFrame instead of AudioFrame
        if not isinstance(frame, InputAudioRawFrame):
            await self.push_frame(frame, direction)
            return
            
        # Buffer the audio
        self.audio_buffer += frame.audio
        current_time = asyncio.get_event_loop().time()
        
        # Check minimum buffer size first
        if len(self.audio_buffer) < self.min_buffer_size:
            await self.push_frame(frame, direction)
            return
        
        # Determine buffered duration
        buffer_duration = len(self.audio_buffer) / (self.params.sample_rate * 2)
        buffer_duration_ms = buffer_duration * 1000

        should_process = False

        if self.params.enable_vad:
            # Improved VAD logic
            rms = audioop.rms(frame.audio, 2) if len(frame.audio) >= 2 else 0
            silent = rms < 300  # Lower threshold for better detection

            if silent:
                if self.silence_start is None:
                    self.silence_start = current_time
                elif (current_time - self.silence_start) * 1000 >= self.params.vad_silence_ms:
                    should_process = True
            else:
                self.silence_start = None
                # Process on longer buffers to avoid short audio errors
                if buffer_duration_ms >= self.params.buffer_duration_ms:
                    should_process = True
        else:
            if buffer_duration_ms >= self.params.buffer_duration_ms:
                should_process = True

        # Add cooldown between processing attempts
        if (should_process and not self.is_processing and 
            current_time - self.last_process_time >= 2.0 and  # 2 second cooldown
            len(self.audio_buffer) >= self.min_buffer_size):
            
            self.is_processing = True
            try:
                text = await self._transcribe_audio(self.audio_buffer)
                if text and text.strip():
                    text_frame = TextFrame(text=text.strip())
                    await self.push_frame(text_frame, direction)
                self.audio_buffer = b""
                self.last_process_time = current_time
            except Exception as e:
                logger.error(f"Error in transcription: {e}")
            finally:
                self.is_processing = False
                
        # Always push the original audio frame
        await self.push_frame(frame, direction)
        
    async def _transcribe_audio(self, audio_data):
        """
        Send audio data to OpenAI's API for transcription.
        """
        try:
            from openai import OpenAI
            
            # Validate audio data size
            if len(audio_data) < self.min_buffer_size:
                logger.debug(f"Audio buffer too small: {len(audio_data)} bytes")
                return ""
            
            # Create the OpenAI client
            client = OpenAI(api_key=self.params.api_key)
            
            # Convert audio data to WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                
                # Create WAV file from audio buffer
                with wave.open(temp_filename, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(self.params.sample_rate)
                    wav_file.writeframes(audio_data)
            
            # Check file size before sending
            file_size = os.path.getsize(temp_filename)
            if file_size < 1024:  # Less than 1KB
                logger.debug(f"WAV file too small: {file_size} bytes")
                os.unlink(temp_filename)
                return ""
            
            # Send to OpenAI API
            with open(temp_filename, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model=self.params.model,
                    file=audio_file,
                    language=self.params.language
                )
            
            # Clean up temp file
            os.unlink(temp_filename)
            
            # Extract and return the transcribed text
            return response.text
            
        except Exception as e:
            logger.error(f"Error transcribing audio with OpenAI: {e}")
            return ""

class VoiceSystem:
    """Voice recognition system for elderly healthcare with the owl robot."""
    
    def __init__(self, event_bus, device_index=None):
        self.event_bus = event_bus
        self.device_index = device_index
        self.runner = None
        self.task = None
        self.pipeline = None
        self.transport = None
        
    async def handle_command(self, command_data):
        """Handle processed voice commands"""
        logger.info(f"Command detected: {json.dumps(command_data)}")
        
        # Generate a text response for TTS
        intent = command_data["intent"]
        response_text = ""
        
        # Generate appropriate responses based on intent
        if intent == "medication_reminder":
            medication = command_data.get("entities", {}).get("medication", "your medication")
            response_text = f"It's time to take {medication}. Would you like me to remind you again in an hour?"
            
        elif intent == "emergency_assistance":
            contact = command_data.get("entities", {}).get("contact", "emergency services")
            response_text = f"I'm contacting {contact} right away. Please stay calm and I'll stay with you."
            
        elif intent == "health_check":
            measure = command_data.get("entities", {}).get("measure", "health")
            response_text = f"Let's check your {measure}. Please follow the instructions on the screen."
            
        elif intent == "social_interaction":
            response_text = "I'm here to keep you company. Would you like to hear a story or perhaps talk about your day?"
            
        elif intent == "system_control":
            action = command_data.get("entities", {}).get("action")
            if action == "volume_up":
                response_text = "I've increased the volume for you."
            elif action == "volume_down":
                response_text = "I've decreased the volume for you."
                
        elif intent == "set_reminder":
            response_text = "I'll remind you. Can you tell me when you need to be reminded?"
            
        elif intent == "general_query":
            query = command_data.get("entities", {}).get("query_text", "")
            response_text = f"Let me find that information for you about: {query}"
            
        else:
            response_text = "I'm sorry, I didn't understand that. Could you please repeat it?"
        
        # Publish the response text for TTS service
        if response_text:
            await self.event_bus.publish("text_received", response_text)
    
    async def setup_pipeline(self):
        """Set up the voice processing pipeline using Pipecat."""
        try:
            logger.info("Beginning voice pipeline setup...")
            
            # Create the transport for audio input with appropriate settings for elderly users
            logger.info("Initializing audio transport...")
            transport_params = LocalAudioTransportParams(
                audio_in_enabled=True,
                audio_in_sample_rate=16000,
                audio_in_channels=1,
                audio_out_enabled=False,
                audio_in_device_index=self.device_index  # Using the correct parameter name
            )
            self.transport = LocalAudioTransport(transport_params)
            logger.info("Audio transport initialized successfully")
            
            # Choose speech recognition service based on configuration
            pipeline_components = [self.transport.input()]
            
            if hasattr(settings, 'speech_recognition_provider') and settings.speech_recognition_provider == SpeechRecognitionProvider.OPENAI:
                logger.info("Initializing OpenAI speech recognition service...")
                
                # Check if we can use the built-in OpenAI service from pipecat
                if HAS_PIPECAT_OPENAI and hasattr(settings, 'openai_api_key'):
                    try:
                        # Try to use the built-in OpenAI service
                        openai_service = OpenAISTTService(
                            OpenAISTTServiceParams(
                                api_key=settings.openai_api_key,
                                model=getattr(settings, 'openai_model', 'whisper-1'),
                                language="en"
                            )
                        )
                        pipeline_components.append(openai_service)
                        logger.info("Using Pipecat's built-in OpenAI STT service")
                    except Exception as e:
                        # Fall back to our custom implementation
                        logger.warning(f"Could not initialize Pipecat's OpenAI service: {e}")
                        logger.info("Falling back to custom OpenAI implementation")
                        openai_processor = OpenAIAudioProcessor(
                            OpenAIAudioProcessor.InputParams(
                                api_key=settings.openai_api_key,
                                model=getattr(settings, 'openai_model', 'whisper-1'),
                                buffer_duration_ms=getattr(settings, 'openai_buffer_duration_ms', 4000),  # Increased
                                enable_vad=getattr(settings, 'openai_enable_vad', True),  # Enabled by default
                                vad_silence_ms=getattr(settings, 'openai_vad_silence_ms', 1000),  # Increased
                                language="en"
                            )
                        )
                        pipeline_components.append(openai_processor)
                else:
                    # Use our custom implementation
                    logger.info("Using custom OpenAI implementation")
                    if not hasattr(settings, 'openai_api_key') or not settings.openai_api_key:
                        logger.warning("OpenAI API key not found in settings, falling back to Whisper")
                        whisper_service = WhisperSTTService(
                            model=Model.DISTIL_MEDIUM_EN,
                            device="cpu",
                            no_speech_prob=0.4
                        )
                        pipeline_components.append(whisper_service)
                    else:
                        openai_processor = OpenAIAudioProcessor(
                            OpenAIAudioProcessor.InputParams(
                                api_key=settings.openai_api_key,
                                model=getattr(settings, 'openai_model', 'whisper-1'),
                                buffer_duration_ms=getattr(settings, 'openai_buffer_duration_ms', 4000),
                                enable_vad=getattr(settings, 'openai_enable_vad', True),
                                vad_silence_ms=getattr(settings, 'openai_vad_silence_ms', 1000),
                                language="en"
                            )
                        )
                        pipeline_components.append(openai_processor)
            else:
                # Default to Whisper
                logger.info("Initializing Whisper STT service...")
                whisper_service = WhisperSTTService(
                    model=Model.DISTIL_MEDIUM_EN,
                    device="cpu",
                    no_speech_prob=0.4
                )
                pipeline_components.append(whisper_service)
                logger.info("Whisper STT service initialized successfully")
            
            # Create NLP service for intent classification
            logger.info("Initializing NLP service...")
            nlp_service = HealthcareNLP(event_bus=self.event_bus)
            pipeline_components.append(nlp_service)
            logger.info("NLP service initialized successfully")
            
            # Create the pipeline with components
            logger.info("Creating pipeline with components...")
            self.pipeline = Pipeline(pipeline_components)
            logger.info("Pipeline created successfully")
            
            # Create a task for the pipeline
            logger.info("Creating pipeline task...")
            self.task = PipelineTask(self.pipeline)
            logger.info("Pipeline task created successfully")
            
            # Create a runner for the task
            logger.info("Creating pipeline runner...")
            self.runner = PipelineRunner(handle_sigint=False)
            logger.info("Pipeline runner created successfully")
            
            logger.info("Voice pipeline setup complete!")
        except Exception as e:
            logger.error(f"Failed to set up voice pipeline: {e}", exc_info=True)
            raise
    
    async def start(self):
        """Start the voice processing pipeline"""
        try:
            logger.info("Setting up voice recognition pipeline...")
            await self.setup_pipeline()
            logger.info("Starting voice recognition system...")
            
            try:
                await self.runner.run(self.task)
                logger.info("Voice recognition system started successfully")
            except asyncio.CancelledError:
                logger.info("Voice recognition task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in voice recognition pipeline: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to start voice recognition system: {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop the voice processing pipeline"""
        try:
            logger.info("Stopping voice recognition system...")
            if self.task:
                logger.info("Cancelling pipeline task...")
                # Properly await the cancel coroutine
                await self.task.cancel()
                            
            logger.info("Voice recognition system stopped successfully")
        except Exception as e:
            logger.error(
                f"Error while stopping voice recognition system: {e}",
                exc_info=True,
            )
            # Don't re-raise as this is cleanup code

    async def pause(self):
        """Pause audio input if supported."""
        try:
            if self.transport:
                if hasattr(self.transport, "pause"):
                    self.transport.pause()
                elif hasattr(self.transport, "pause_input"):
                    self.transport.pause_input()
            logger.info("Voice system paused")
        except Exception as e:
            logger.error(f"Failed to pause voice system: {e}")

    async def resume(self):
        """Resume audio input if supported."""
        try:
            if self.transport:
                if hasattr(self.transport, "resume"):
                    self.transport.resume()
                elif hasattr(self.transport, "resume_input"):
                    self.transport.resume_input()
            logger.info("Voice system resumed")
        except Exception as e:
            logger.error(f"Failed to resume voice system: {e}")
