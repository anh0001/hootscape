# voice/recognition.py
import asyncio
import os
from typing import Callable, Dict, Any, Optional
import json
import logging

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import TextFrame
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.transports.base_transport import TransportParams
from pipecat.services.whisper import WhisperSTTService, Model
from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter
from pipecat.processors.frame_processor import FrameProcessor
from pydantic import Field, BaseModel

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
    
    def __init__(self, params: InputParams = None, **kwargs):
        # Initialize parent properly
        super().__init__(**kwargs)
        
        # Create parameters if none provided
        self.nlp_params = params or self.InputParams()
        
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
        
        # Publish to event bus to notify other components
        await self.event_bus.publish("voice_command", command_data)
        
        # Also publish text response for TTS
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
            
            # Initialize WhisperSTTService with appropriate settings
            logger.info("Initializing Whisper STT service...")
            whisper_service = WhisperSTTService(
                model=Model.DISTIL_MEDIUM_EN,  # Using a pre-trained distilled model optimized for English
                device="cpu",                  # Explicitly set to CPU mode
                no_speech_prob=0.4             # Threshold for detecting no speech
            )
            logger.info("Whisper STT service initialized successfully")
            
            # Create NLP service for intent classification
            logger.info("Initializing NLP service...")
            nlp_service = HealthcareNLP(
                HealthcareNLP.InputParams(command_handler=self.handle_command)
            )
            logger.info("NLP service initialized successfully")
            
            # Create the pipeline with components
            logger.info("Creating pipeline with components...")
            self.pipeline = Pipeline([
                self.transport.input(),  # Audio input
                whisper_service,         # Speech recognition
                nlp_service              # Intent classification
            ])
            logger.info("Pipeline created successfully")
            
            # Create a task for the pipeline
            logger.info("Creating pipeline task...")
            self.task = PipelineTask(self.pipeline)
            logger.info("Pipeline task created successfully")
            
            # Create a runner for the task
            logger.info("Creating pipeline runner...")
            # Create a runner for the task with signal handling disabled
            self.runner = PipelineRunner(handle_sigint=False)
            # self.runner = PipelineRunner()
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
            
            # Add try/finally to ensure proper cleanup even if runner.run raises exception
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
                
                # No need to shield or wait for the task again as cancel() already handles that
                    
            if self.runner:
                logger.info("Stopping pipeline runner...")
                try:
                    await asyncio.wait_for(self.runner.stop(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("Runner stop timed out")
                    
            if self.transport:
                logger.info("Closing audio transport...")
                try:
                    await asyncio.wait_for(self.transport.close(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("Transport close timed out")
                    
            logger.info("Voice recognition system stopped successfully")
        except Exception as e:
            logger.error(f"Error while stopping voice recognition system: {e}", exc_info=True)
            # Don't re-raise as this is cleanup code