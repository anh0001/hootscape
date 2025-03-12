# voice/commands/handlers.py
import asyncio
import logging
import json
import datetime
import random
from typing import Dict, Any, List

logger = logging.getLogger("healthcare_handlers")

class HealthcareCommands:
    """
    Healthcare-specific command handlers for elderly care.
    This class contains the business logic for responding to healthcare-related
    voice commands from elderly users.
    """
    
    def __init__(self, event_bus, owl_controller, tts_service):
        self.event_bus = event_bus
        self.owl = owl_controller
        self.tts_service = tts_service
        self.reminders = []
        self.medications = {}
        self.vitals_history = {}
        self.emergency_contacts = {
            "caregiver": "555-0100",
            "doctor": "555-0101",
            "emergency": "911",
            "family": "555-0102",
        }
        
        # Subscribe to voice command events
        self.event_bus.subscribe("voice_command", self.handle_voice_command)
        
    async def handle_voice_command(self, command_data):
        """
        Process voice commands related to healthcare
        """
        intent = command_data.get("intent", "unknown")
        entities = command_data.get("entities", {})
        original_text = command_data.get("original_text", "")
        
        logger.info(f"Healthcare handler processing intent: {intent}")
        
        # Dispatch to the appropriate handler method
        handlers = {
            "medication_reminder": self.handle_medication_reminder,
            "emergency_assistance": self.handle_emergency,
            "health_check": self.handle_health_check,
            "social_interaction": self.handle_social_interaction,
            "set_reminder": self.handle_set_reminder,
            "general_query": self.handle_general_query
        }
        
        handler = handlers.get(intent)
        if handler:
            # Call the appropriate handler with the command data
            try:
                await handler(entities, original_text)
            except Exception as e:
                logger.error(f"Error in handler {intent}: {e}")
                await self.text_and_movement("I'm having trouble processing that request. Let me try again.")
        else:
            # Unknown intent, give a friendly response
            await self.text_and_movement(
                "I'm not sure what you need. You can ask me about medications, " +
                "health checks, or say 'help' if you need assistance.",
                [{"type": 5, "duration": 1}, {"type": 6, "duration": 1}]  # A gentle head tilt
            )
    
    async def handle_medication_reminder(self, entities, original_text):
        """Handle medication reminder requests"""
        medication = entities.get("medication", "your medication")
        
        # Check if this is a request to set up a reminder
        if "remind" in original_text or "remember" in original_text:
            # Schedule a reminder for this medication
            await self.text_and_movement(
                f"I'll remind you to take {medication}. What time should I remind you?",
                [{"type": 3, "duration": 1}]  # Turn right
            )
            # In a real implementation, we would now listen for a time and set up the reminder
        
        # If they're asking if it's time for medication
        elif "time" in original_text or "should" in original_text:
            # Here we could check against a schedule
            await self.text_and_movement(
                f"It's time to take {medication}. Would you like me to mark it as taken?",
                [{"type": 5, "duration": 1}, {"type": 6, "duration": 1}]  # Head movement
            )
        
        # Default response
        else:
            await self.text_and_movement(
                f"Your medication {medication} is important. Let me know if you need a reminder.",
                [{"type": 1, "duration": 1}]  # Tilt forward
            )
    
    async def handle_emergency(self, entities, original_text):
        """Handle emergency assistance requests"""
        contact = entities.get("contact", "emergency services")
        contact_number = self.emergency_contacts.get(contact, self.emergency_contacts["emergency"])
        
        # Make owl movements to indicate urgency and concern
        movements = [
            {"type": 5, "duration": 0.5},
            {"type": 6, "duration": 0.5},
            {"type": 5, "duration": 0.5},
            {"type": 6, "duration": 0.5}
        ]
        
        await self.text_and_movement(
            f"I understand this is an emergency. I'm contacting {contact} at {contact_number} right away. " +
            "Please stay where you are and remain calm.",
            movements
        )
        
        # In a real implementation, we would integrate with a calling service
        # For now, we'll simulate the process
        await asyncio.sleep(2)
        await self.text_and_movement(
            f"I've reached out to {contact}. Help is on the way. I'll stay with you.",
            [{"type": 1, "duration": 1}]  # Reassuring forward tilt
        )
    
    async def handle_health_check(self, entities, original_text):
        """Handle health check-in requests"""
        measure = entities.get("measure", "general health")
        
        # Different responses based on the health measure
        if measure == "blood pressure":
            await self.text_and_movement(
                "Let's check your blood pressure. Please put on the cuff and " +
                "press the button when you're ready.",
                [{"type": 3, "duration": 1}]  # Rotate right
            )
            
        elif measure in ["sugar", "glucose"]:
            await self.text_and_movement(
                "Time to check your blood sugar. Please use your glucose meter and " +
                "let me know the reading when you're done.",
                [{"type": 4, "duration": 1}]  # Rotate left
            )
            
        elif measure in ["temperature", "fever"]:
            await self.text_and_movement(
                "Let's check if you have a fever. Please use the thermometer " +
                "and tell me your temperature when it's ready.",
                [{"type": 1, "duration": 1}]  # Tilt forward
            )
            
        elif measure == "heart rate":
            await self.text_and_movement(
                "Let's check your heart rate. Please place your finger on the sensor " +
                "and remain still for 30 seconds.",
                [{"type": 2, "duration": 1}]  # Tilt back
            )
            
        else:
            # General health check
            await self.text_and_movement(
                "How are you feeling today? Are you experiencing any pain, " +
                "discomfort, or unusual symptoms?",
                [{"type": 5, "duration": 1}, {"type": 6, "duration": 1}]  # Head movements
            )
    
    async def handle_social_interaction(self, entities, original_text):
        """Handle requests for social interaction"""
        # Choose a random conversation starter
        starters = [
            "How has your day been so far?",
            "Would you like to hear an interesting fact?",
            "Would you like to hear about the weather today?",
            "Is there anything specific you'd like to talk about?",
            "Would you like me to tell you a short story?",
            "Have you spoken with your family recently?",
            "Did you watch any good shows or movies lately?"
        ]
        
        choice = random.choice(starters)
        
        # Gentle, friendly owl movement
        movements = [
            {"type": 5, "duration": 0.7},
            {"type": 6, "duration": 0.7},
            {"type": 1, "duration": 0.7}
        ]
        
        await self.text_and_movement(
            f"I'm here to keep you company. {choice}",
            movements
        )
    
    async def handle_set_reminder(self, entities, original_text):
        """Handle setting reminders"""
        # In a real implementation, we would parse time and event
        # For this example, we'll use a simple acknowledgment
        
        await self.text_and_movement(
            "I'll set a reminder for you. What would you like me to remind you about, and when?",
            [{"type": 3, "duration": 1}]  # Rotate right
        )
        
        # We would then wait for the response and process it
        # This would involve detecting times/dates in the text
    
    async def handle_general_query(self, entities, original_text):
        """Handle general questions"""
        query_text = entities.get("query_text", "")
        
        # Simple responses to common questions
        if "time" in query_text:
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            await self.text_and_movement(
                f"The current time is {current_time}.",
                [{"type": 3, "duration": 1}]  # Rotate right
            )
            
        elif "day" in query_text or "date" in query_text:
            current_date = datetime.datetime.now().strftime("%A, %B %d")
            await self.text_and_movement(
                f"Today is {current_date}.",
                [{"type": 4, "duration": 1}]  # Rotate left
            )
            
        elif "weather" in query_text:
            # In a real implementation, we would integrate with a weather API
            await self.text_and_movement(
                "I don't have current weather information, but I can help you check the forecast on your device.",
                [{"type": 2, "duration": 1}]  # Tilt back
            )
            
        else:
            await self.text_and_movement(
                "I'm not sure about that. Could you ask me in a different way?",
                [{"type": 5, "duration": 0.5}, {"type": 6, "duration": 0.5}]  # Head tilt
            )
    
    async def text_and_movement(self, text, movements=None):
        """
        Helper method to coordinate text-to-speech and owl movements
        """
        tasks = []
        
        # Add TTS task
        if text:
            tasks.append(self.event_bus.publish("text_received", text))
        
        # Add movement task if provided
        if movements:
            tasks.append(self.event_bus.publish("owl_movements", movements))
        
        # Execute both concurrently
        if tasks:
            await asyncio.gather(*tasks)