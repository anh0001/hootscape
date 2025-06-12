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

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import TextFrame, InputAudioRawFrame, OutputAudioRawFrame  # Updated import
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.transports.base_transport import TransportParams
from pipecat.services.whisper import WhisperSTTService, Model
from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter
from pipecat.processors.frame_processor import FrameProcessor
from pydantic import BaseModel, ConfigDictfrom core.event_bus
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
    
    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        
        if not isinstance(frame, TextFrame):
            await self.push_frame(frame, direction)
            return
            
        text = frame.text.lower().strip()
        logger.info(f"Processing text: {text}")
        
        # Skip processing if empty
        if not text:
            await self.push_frame(frame, direction)
            return
            
        # Check for wake word first
        wake_words = ["hey owl", "hello owl", "owl", "hey there"]
        is_wake_word = any(text.startswith(word) for word in wake_words)
        
        # If wake word detected, clean the text
        if is_wake_word:
            for word in wake_words:
                if text.startswith(word):
                    text = text[len(word):].strip()
                    break
        else:
            # No wake word, don't process further
            await self.push_frame(frame, direction)
            return
            
        # Basic intent classification for healthcare
        intent = "unknown"
        entities = {}
        
        # Medication reminders
        if any(word in text for word in ["medicine", "medication", "pill", "pills", "drug"]):
            intent = "medication_reminder"
            # Extract medication name if present
            # This is a simple implementation - could be enhanced with better NLP
            if "take" in text:
                parts = text.split("take")
                if len(parts) > 1:
                    entities["medication"] = parts[1].strip()
                    
        # Emergency help
        elif any(word in text for word in ["help", "emergency", "fall", "fallen", "hurt"]):
            intent = "emergency_assistance"
            if "call" in text:
                for family in ["daughter", "son", "doctor", "nurse", "caregiver"]:
                    if family in text:
                        entities["contact"] = family
                        
        # Health check-in
        elif any(phrase in text for phrase in ["how am i", "my health", "feeling", "check up"]):
            intent = "health_check"
            for measure in ["blood pressure", "temperature", "heart rate", "sugar", "glucose"]:
                if measure in text:
                    entities["measure"] = measure
                    
        # Social interaction
        elif any(word in text for word in ["lonely", "alone", "talk", "chat", "bored"]):
            intent = "social_interaction"
            
        # System control
        elif any(word in text for word in ["louder", "volume up", "turn up"]):
            intent = "system_control"
            entities["action"] = "volume_up"
        elif any(word in text for word in ["quieter", "volume down", "turn down"]):
            intent = "system_control"
            entities["action"] = "volume_down"
            
        # Reminders
        elif any(word in text for word in ["remind", "remember", "forget", "appointment"]):
            intent = "set_reminder"
            # Could extract time/date here with more sophisticated parsing
        
        # General queries
        elif any(word in text for word in ["what", "when", "how", "who", "where"]):
            intent = "general_query"
            entities["query_text"] = text
            
        result = {
            "intent": intent,
            "entities": entities,
            "original_text": text
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
        """Handle processed voice commands with options for synchronized speech"""
        logger.info(f"Command detected: {json.dumps(command_data)}")
        
        # Publish to event bus to notify other components
        await self.event_bus.publish("voice_command", command_data)
        
        # Get intent and entities
        intent = command_data["intent"]
        entities = command_data.get("entities", {})
        response_text = ""
        
        # Generate response based on intent
        if intent == "medication_reminder":
            medication = entities.get("medication", "your medication")
            response_text = f"It's time to take {medication}. Would you like me to remind you again in an hour?"
        elif intent == "emergency_assistance":
            contact = entities.get("contact", "emergency services")
            response_text = f"I'm contacting {contact} right away. Please stay calm and I'll stay with you."
        elif intent == "health_check":
            measure = entities.get("measure", "health")
            response_text = f"Let's check your {measure}. Please follow the instructions on the screen."
        elif intent == "social_interaction":
            response_text = "I'm here to keep you company. Would you like to hear a story or perhaps talk about your day?"
        elif intent == "system_control":
            action = entities.get("action")
            if action == "volume_up":
                response_text = "I've increased the volume for you."
            elif action == "volume_down":
                response_text = "I've decreased the volume for you."
        elif intent == "set_reminder":
            response_text = "I'll remind you. Can you tell me when you need to be reminded?"
        elif intent == "general_query":
            # For general queries, try to use OpenAI if available
            original_text = command_data.get("original_text", "")
            if hasattr(settings, 'speech_recognition_provider') and \
               settings.speech_recognition_provider == SpeechRecognitionProvider.OPENAI and \
               settings.openai_api_key:
                context = f"Intent detected: {intent}. Entities: {entities}"
                from api.owl_api_controller import generate_response_with_openai
                response_text = await generate_response_with_openai(original_text, context)
            else:
                response_text = self.generate_simple_response(intent, entities, original_text)
        else:
            # If no predefined response, generate one
            original_text = command_data.get("original_text", "")
            if hasattr(settings, 'speech_recognition_provider') and \
               settings.speech_recognition_provider == SpeechRecognitionProvider.OPENAI and \
               settings.openai_api_key:
                context = f"Intent detected: {intent}. Entities: {entities}"
                from api.owl_api_controller import generate_response_with_openai
                response_text = await generate_response_with_openai(original_text, context)
            else:
                response_text = self.generate_simple_response(intent, entities, original_text)
        
        # Based on settings, choose synchronized or regular TTS
        if response_text:
            if hasattr(settings, 'enable_synchronized_movements') and settings.enable_synchronized_movements and \
               settings.openai_api_key:
                await self.send_synchronized_speech(response_text)
            else:
                # Use the original event bus approach for TTS
                await self.event_bus.publish("text_received", response_text)
    
    def generate_simple_response(self, intent, entities, original_text):
        """Generate a simple response when OpenAI isn't available"""
        # Simple template-based responses
        if "help" in original_text.lower():
            return "I'm here to help. You can ask me about medications, health checks, or emergency assistance."
        
        if any(word in original_text.lower() for word in ["thank", "thanks"]):
            return "You're welcome. I'm happy to assist you."
        
        # Default responses by intent
        intent_responses = {
            "unknown": "I'm not sure I understood. Could you please rephrase that?",
            "medication_reminder": "I can help you with your medication schedule.",
            "emergency_assistance": "Do you need emergency help? I can contact someone for you.",
            "health_check": "I can help monitor your health. What would you like to check?",
            "social_interaction": "I'm here to keep you company. How are you feeling today?",
            "set_reminder": "I'd be happy to set a reminder for you.",
            "general_query": "I'll try to answer your question as best I can."
        }
        
        return intent_responses.get(intent, "How can I help you today?")
    
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
        buffer_duration_ms: int = Field(default=3000, description="Duration of audio to buffer before processing (ms)")
        enable_vad: bool = Field(default=False, description="Enable VAD based buffering")
        vad_silence_ms: int = Field(default=800, description="Required silence duration to trigger processing (ms)")
        sample_rate: int = Field(default=16000, description="Sample rate of the audio")
        language: str = Field(default="en", description="Language code")
        
    def __init__(self, params: InputParams = None, **kwargs):
        super().__init__(**kwargs)
        self.params = params or self.InputParams()
        self.audio_buffer = b""
        self.last_process_time = 0
        self.is_processing = False
        self.silence_start = None
        
    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        
        # Only process InputAudioRawFrame instead of AudioFrame
        if not isinstance(frame, InputAudioRawFrame):
            await self.push_frame(frame, direction)
            return
            
        # Buffer the audio
        self.audio_buffer += frame.audio
        current_time = asyncio.get_event_loop().time()
        
        # Determine buffered duration
        buffer_duration = len(self.audio_buffer) / (self.params.sample_rate * 2)
        buffer_duration_ms = buffer_duration * 1000

        should_process = False

        if self.params.enable_vad:
            rms = audioop.rms(frame.audio, 2) if len(frame.audio) >= 2 else 0
            silent = rms < 500

            if silent:
                if self.silence_start is None:
                    self.silence_start = current_time
                elif (current_time - self.silence_start) * 1000 >= self.params.vad_silence_ms:
                    should_process = True
            else:
                self.silence_start = None
                if buffer_duration_ms >= self.params.buffer_duration_ms:
                    should_process = True
        else:
            if buffer_duration_ms >= self.params.buffer_duration_ms:
                should_process = True

        if (should_process and not self.is_processing and current_time - self.last_process_time >= 1.0):
            self.is_processing = True
            try:
                text = await self._transcribe_audio(self.audio_buffer)
                if text:
                    text_frame = TextFrame(text=text)
                    await self.push_frame(text_frame, direction)
                self.audio_buffer = b""
                self.last_process_time = current_time
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
                                buffer_duration_ms=getattr(settings, 'openai_buffer_duration_ms', 3000),
                                enable_vad=getattr(settings, 'openai_enable_vad', False),
                                vad_silence_ms=getattr(settings, 'openai_vad_silence_ms', 800),
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
                                buffer_duration_ms=getattr(settings, 'openai_buffer_duration_ms', 3000),
                                enable_vad=getattr(settings, 'openai_enable_vad', False),
                                vad_silence_ms=getattr(settings, 'openai_vad_silence_ms', 800),
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
