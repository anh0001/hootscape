# utils/speech_movement_sync.py
import asyncio
import re
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI, AsyncOpenAI
import time

logger = logging.getLogger("speech_movement_sync")

class SpeechMovementSync:
    """
    Handles synchronized speech and movement execution.
    Processes text, analyzes with OpenAI, and executes coordinated speech and movements.
    """
    
    def __init__(self, tts_service, owl_controller, openai_api_key, model="gpt-3.5-turbo"):
        self.tts_service = tts_service
        self.owl = owl_controller
        self.openai_api_key = openai_api_key
        self.model = model
        self.movement_map = {
            1: self.owl.tilt_front,
            2: self.owl.tilt_back,
            3: self.owl.rotate_right,
            4: self.owl.rotate_left,
            5: self.owl.tilt_right,
            6: self.owl.tilt_left,
        }
    
    async def process_text(self, text: str) -> bool:
        """
        Process text by analyzing, parsing, and executing speech with synchronized movements.
        
        Args:
            text: The text to process
            
        Returns:
            bool: True if successfully processed, False otherwise
        """
        try:
            # Step 1: Analyze text with OpenAI to add movement markers
            logger.info(f"Analyzing text with OpenAI: {text[:50]}...")
            annotated_text = await self._analyze_with_openai(text)
            
            if not annotated_text:
                logger.warning("Failed to get annotated text from OpenAI")
                return False
                
            logger.info(f"Received annotated text: {annotated_text[:50]}...")
            
            # Step 2: Parse the annotated text into segments
            segments = self._parse_annotated_text(annotated_text)
            
            if not segments:
                logger.warning("No segments found in annotated text")
                return False
                
            logger.info(f"Parsed {len(segments)} segments")
            
            # Step 3: Execute the segments as a sequence
            await self._execute_sequence(segments)
            return True
            
        except Exception as e:
            logger.error(f"Error processing text: {e}", exc_info=True)
            return False
    
    async def _analyze_with_openai(self, text: str) -> Optional[str]:
        """
        Use OpenAI to analyze text and add movement markers.
        
        Args:
            text: Text to analyze
            
        Returns:
            Optional[str]: Annotated text with movement markers, or None if failed
        """
        if not self.openai_api_key:
            logger.error("No OpenAI API key provided")
            return None
            
        try:
            client = AsyncOpenAI(api_key=self.openai_api_key)
            
            prompt = f"""
            Analyze the following text for an owl robot and add appropriate movement markers to create a natural, expressive delivery.
            
            AVAILABLE MOVEMENTS:
            - [TLTFRONT,duration] - Tilt forward (like nodding)
            - [TLTBACK,duration] - Tilt backward (like looking up)
            - [ROTRIGHT,duration] - Rotate head right
            - [ROTLEFT,duration] - Rotate head left
            - [TLTRIGHT,duration] - Tilt head right
            - [TLTLEFT,duration] - Tilt head left
            
            GUIDELINES:
            - Insert movements at natural pauses (commas, periods)
            - Use durations between 0.5 and 1.5 seconds
            - Match movements to emotional content
            - Don't overdo it - use 1-2 movements per sentence
            - IMPORTANT: Return ONLY the text with markers inserted
            
            TEXT TO ENHANCE:
            {text}
            """
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You add owl movement markers to text. Return ONLY the text with markers inserted."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            result = response.choices[0].message.content.strip()
            return result
            
        except Exception as e:
            logger.error(f"Error in OpenAI analysis: {e}", exc_info=True)
            return None
    
    def _parse_annotated_text(self, annotated_text: str) -> List[Dict[str, Any]]:
        """
        Parse annotated text into a sequence of speech and movement segments.
        
        Args:
            annotated_text: Text with movement markers
            
        Returns:
            List[Dict[str, Any]]: List of speech and movement segments
        """
        # Define regex pattern for movement markers
        pattern = r'\[(TLT(?:FRONT|BACK)|ROT(?:RIGHT|LEFT)|TLT(?:RIGHT|LEFT)),(\d+\.?\d*)\]'
        
        # Map text movement names to numeric movement types
        movement_name_map = {
            "TLTFRONT": 1,
            "TLTBACK": 2, 
            "ROTRIGHT": 3,
            "ROTLEFT": 4,
            "TLTRIGHT": 5,
            "TLTLEFT": 6
        }
        
        # Find all markers in the text
        matches = list(re.finditer(pattern, annotated_text))
        
        # If no markers found, return the whole text as one speech segment
        if not matches:
            return [{"type": "speech", "text": annotated_text}]
        
        # Process text segments and movement markers
        segments = []
        last_end = 0
        
        for match in matches:
            # Add text before this marker
            text_before = annotated_text[last_end:match.start()].strip()
            if text_before:
                segments.append({"type": "speech", "text": text_before})
            
            # Extract movement info
            movement_name = match.group(1)
            try:
                duration = float(match.group(2))
            except ValueError:
                duration = 1.0
                
            # Add movement segment
            movement_type = movement_name_map.get(movement_name)
            if movement_type:
                segments.append({
                    "type": "movement",
                    "movement_type": movement_type,
                    "duration": duration
                })
            
            last_end = match.end()
        
        # Add remaining text after the last marker
        final_text = annotated_text[last_end:].strip()
        if final_text:
            segments.append({"type": "speech", "text": final_text})
        
        return segments
    
    async def _execute_sequence(self, segments: List[Dict[str, Any]]) -> None:
        """
        Execute a sequence of speech and movement segments.
        
        Args:
            segments: List of segments to execute
        """
        current_speech = ""
        
        for i, segment in enumerate(segments):
            if segment["type"] == "speech":
                # Accumulate speech text
                current_speech += " " + segment["text"]
                
                # If next segment is a movement or this is the last segment, speak the accumulated text
                if i == len(segments) - 1 or segments[i+1]["type"] == "movement":
                    if current_speech.strip():
                        logger.info(f"Speaking: {current_speech[:50]}...")
                        # Execute speech in a separate thread to avoid blocking
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self.tts_service.play_text, current_speech.strip())
                        current_speech = ""  # Reset accumulated speech
                
            elif segment["type"] == "movement":
                # Execute movement
                movement_type = segment["movement_type"]
                duration = segment["duration"]
                
                move_func = self.movement_map.get(movement_type)
                if move_func:
                    logger.info(f"Executing movement: {movement_type} for {duration}s")
                    await move_func()
                    await asyncio.sleep(duration)