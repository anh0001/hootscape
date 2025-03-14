from aiohttp import web
import asyncio
import logging
import re
import os
import json
from robot.owl_controller import OwlController  # use the existing class
from config.settings import settings  # Import settings
from utils.speech_movement_sync import SpeechMovementSync

logger = logging.getLogger(__name__)

# Helper function to execute a movement
async def execute_movement(owl, movement_type, duration=1.0):
    """Execute a single owl movement"""
    movement_map = {
        1: owl.tilt_front,
        2: owl.tilt_back,
        3: owl.rotate_right,
        4: owl.rotate_left,
        5: owl.tilt_right,
        6: owl.tilt_left,
    }
    
    move_func = movement_map.get(movement_type)
    if move_func:
        logger.info(f"Executing movement: {movement_type}, duration: {duration}")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, move_func)
        # Return immediately without waiting for the full duration
        # This allows speech to start while movement is still in progress
        return True
    else:
        logger.warning(f"Invalid movement type: {movement_type}")
        return False

# Helper function to execute a sequence of movements
async def execute_movement_sequence(owl, movements):
    for move in movements:
        move_type = move.get("type")
        # Removed duration sleep
        await execute_movement(owl, move_type)
        # No sleep delay between movements

async def handle_owl_command(request):
    data = await request.json()
    loop = asyncio.get_running_loop()
    
    # Combined execution if both speech and movements are provided.
    if "speech" in data and "movements" in data:
        speech_text = data["speech"].get("text", "")
        movements = data["movements"]
        tasks = []
        if speech_text:
            tasks.append(loop.run_in_executor(None, request.app["tts_service"].play_text, speech_text))
        tasks.append(execute_movement_sequence(request.app["owl"], movements))
        await asyncio.gather(*tasks)
        return web.json_response({"status": "commands executed concurrently"})
        
    # Process speech command if provided alone.
    if "speech" in data:
        speech = data["speech"]
        text = speech.get("text", "")
        if text:
            await request.app["event_bus"].publish("text_received", text)
    
    # Process sequence of movements if provided.
    if "movements" in data:
        movements = data["movements"]
        asyncio.create_task(execute_movement_sequence(request.app["owl"], movements))
    # Process macro command by mapping a name to a sequence.
    elif "macro" in data:
        macro = data["macro"]
        if macro == "happy":
            sequence = [
                {"type": 5, "duration": 1},
                {"type": 6, "duration": 1},
                {"type": 5, "duration": 1},
                {"type": 6, "duration": 1},
                {"type": 5, "duration": 1},
                {"type": 6, "duration": 1},
            ]
            asyncio.create_task(execute_movement_sequence(request.app["owl"], sequence))
        else:
            return web.Response(text="Unknown macro", status=400)
    # Fallback for legacy single movement (optional)
    elif "movement" in data:
        movement = data["movement"]
        move_type = movement.get("type")
        movement_map = {
            1: request.app["owl"].tilt_front,
            2: request.app["owl"].tilt_back,
            3: request.app["owl"].rotate_right,
            4: request.app["owl"].rotate_left,
            5: request.app["owl"].tilt_right,
            6: request.app["owl"].tilt_left,
        }
        move_func = movement_map.get(move_type)
        if move_func:
            loop.run_in_executor(None, move_func)
        else:
            return web.Response(text="Invalid movement type", status=400)
    return web.json_response({"status": "command received"})

async def analyze_with_openai(text, api_key, model="gpt-3.5-turbo"):
    """Send text to OpenAI to analyze and add movement markers."""
    try:
        from openai import OpenAI
        import json
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        Your task is to analyze this text and create a natural sequence of owl robot movements followed by speech.

        The owl robot can make 6 types of movements:
        1. Tilt forward (like nodding) - best for agreement, confirmation
        2. Tilt backward (like looking up) - best for questions, curiosity
        3. Rotate right - good for transitions, shifting topics
        4. Rotate left - also good for transitions
        5. Tilt right - good for listening, consideration
        6. Tilt left - also good for listening, consideration

        FORMAT YOUR RESPONSE AS A JSON OBJECT with pairs of:
        1. "movements": Array of movement objects, each with "type" (1-6) and "duration" (0.5-1.5 seconds)
        2. "text_segments": Array of text segments to speak

        IMPORTANT: For a natural interaction, each movement should occur BEFORE its related text segment. 
        The owl should move first, then speak. This creates a more natural, human-like interaction pattern where
        gestures often precede speech.

        Structure your response with alternating pairs:
        - First movement
        - First text segment
        - Second movement
        - Second text segment
        - Etc.

        Make sure each section of text has an associated movement that makes sense for its emotional content.

        Text to analyze: {text}
        """
        
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You analyze text and recommend owl robot movements. Return ONLY valid JSON in the format specified."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        logger.info(f"Received OpenAI response: {result[:100]}...")
        
        # Parse the JSON response
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse OpenAI response as JSON: {result}")
            return None
            
    except Exception as e:
        logger.error(f"Error in OpenAI analysis: {e}", exc_info=True)
        return None

# Keep legacy function for backward compatibility
async def analyze_with_openai_json(text):
    """
    Send text to OpenAI to analyze and return a JSON structure with speech segments
    and movement commands instead of inserting markers into the text.
    """
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        if not api_key:
            logger.warning("OpenAI API key not found, returning original text")
            return {"speech_segments": [text], "movements": []}
            
        client = OpenAI(api_key=api_key)
        
        model = settings.movement_analysis_model if hasattr(settings, 'movement_analysis_model') else "gpt-3.5-turbo"
        
        # Use the new analyze_with_openai function instead
        result = await analyze_with_openai(text, api_key, model)
        
        # Convert the result format if needed
        if result and "text_segments" in result:
            # Map to the old format for backward compatibility
            return {
                "speech_segments": result.get("text_segments", []),
                "movements": result.get("movements", [])
            }
        
        # Fallback to old implementation
        # ...existing code...
    except Exception as e:
        logger.error(f"Error analyzing text with OpenAI JSON: {e}")
        return {"speech_segments": [text], "movements": []}  # Return original text if analysis fails

def parse_annotated_text(annotated_text):
    """
    Parse text with movement markers into a sequence of speech and movement segments.
    """
    # Define the pattern for movement markers
    pattern = r'\[(TLT(?:FRONT|BACK)|ROT(?:RIGHT|LEFT)|TLT(?:RIGHT|LEFT)),(\d+\.?\d*)\]'
    
    # Map movement names to movement types
    movement_map = {
        "TLTFRONT": 1,
        "TLTBACK": 2,
        "ROTRIGHT": 3,
        "ROTLEFT": 4,
        "TLTRIGHT": 5,
        "TLTLEFT": 6
    }
    
    # Find all movement markers
    matches = list(re.finditer(pattern, annotated_text))
    
    sequence = []
    last_end = 0
    
    # Process each marker and the text before it
    for match in matches:
        # Add speech segment before this marker
        speech_text = annotated_text[last_end:match.start()].strip()
        if speech_text:
            sequence.append({"type": "speech", "text": speech_text})
        
        # Add movement
        movement_name = match.group(1)
        duration = float(match.group(2))
        movement_type = movement_map.get(movement_name)
        if movement_type:
            sequence.append({"type": "movement", "movement": {"type": movement_type, "duration": duration}})
        
        last_end = match.end()
    
    # Add any remaining text
    final_text = annotated_text[last_end:].strip()
    if (final_text):
        sequence.append({"type": "speech", "text": final_text})
    
    return sequence

async def execute_speech_movement_sequence(tts_service, owl, sequence):
    """
    Execute a sequence of speech and movement segments.
    """
    loop = asyncio.get_running_loop()
    
    for item in sequence:
        if item["type"] == "speech":
            # Execute speech in a background task
            await loop.run_in_executor(None, tts_service.play_text, item["text"])
        elif item["type"] == "movement":
            movement = item["movement"]
            movement_map = {
                1: owl.tilt_front,
                2: owl.tilt_back,
                3: owl.rotate_right,
                4: owl.rotate_left,
                5: owl.tilt_right,
                6: owl.tilt_left,
            }
            
            move_func = movement_map.get(movement["type"])
            if move_func:
                # Execute movement - no sleep delay
                await loop.run_in_executor(None, move_func)
                # Removed: await asyncio.sleep(movement["duration"])

async def execute_structured_sequence(tts_service, owl, sequence_data):
    """
    Legacy function for backward compatibility.
    Execute a sequence of speech segments and movements based on the structured data.
    """
    try:
        loop = asyncio.get_running_loop()
        speech_segments = sequence_data.get("speech_segments", [])
        movements = sequence_data.get("movements", [])
        
        if not speech_segments:
            logger.warning("No speech segments provided")
            return False
            
        movement_map = {
            1: owl.tilt_front,
            2: owl.tilt_back,
            3: owl.rotate_right,
            4: owl.rotate_left,
            5: owl.tilt_right,
            6: owl.tilt_left,
        }
        
        # Pair movements with speech segments
        for i in range(min(len(speech_segments), len(movements) + 1)):
            # Execute movement before speech if available
            if i < len(movements):
                movement = movements[i]
                move_type = movement.get("type")
                move_func = movement_map.get(move_type)
                
                if move_func:
                    logger.info(f"Executing movement: type={move_type}")
                    # Start the movement
                    await loop.run_in_executor(None, move_func)
                    # Removed: await asyncio.sleep(0.3)
            
            # Speak the corresponding segment immediately after movement begins
            if i < len(speech_segments) and speech_segments[i]:
                logger.info(f"Speaking segment: '{speech_segments[i]}'")
                await loop.run_in_executor(None, tts_service.play_text, speech_segments[i])
                
                # Removed: await asyncio.sleep(0.2)
        
        return True
    except Exception as e:
        logger.error(f"Error executing structured sequence: {e}")
        return False

async def generate_response_with_openai(input_text, context=None):
    """
    Generate a response with OpenAI when no predefined response exists.
    """
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        if not api_key:
            logger.warning("OpenAI API key not found, returning fallback response")
            return "I'm sorry, I'm having trouble processing that right now. Can I help you with something else?"
            
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        Generate a friendly, helpful response for an elderly healthcare companion robot (owl).
        The robot should sound gentle, patient, and reassuring.
        User input: {input_text}
        """
        
        if context:
            prompt += f"\nContext: {context}"
        
        model = settings.movement_analysis_model if hasattr(settings, 'movement_analysis_model') else "gpt-3.5-turbo"
        
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": "You are a friendly healthcare companion owl robot that helps elderly users."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating response with OpenAI: {e}")
        return "I'm sorry, I'm having trouble processing that right now. Can I help you with something else?"

async def handle_synchronized_speech(request):
    """
    Handle synchronized speech and movement requests.
    This improved version uses a direct JSON parsing approach
    rather than text marker parsing and processes in the background.
    """
    data = await request.json()
    text = data.get("text", "")
    
    if not text:
        return web.Response(text="No text provided", status=400)
    
    # Check if OpenAI API key is available
    openai_api_key = settings.openai_api_key
    if not openai_api_key:
        logger.warning("No OpenAI API key available for synchronized speech")
        # Fallback to regular TTS
        await request.app["event_bus"].publish("text_received", text)
        return web.json_response({"status": "fallback_to_tts", "reason": "no_api_key"})
    
    # Get the model to use
    model = getattr(settings, 'movement_analysis_model', 'gpt-3.5-turbo')
    
    # Start a background task for processing
    asyncio.create_task(process_synchronized_speech(
        request.app["tts_service"],
        request.app["owl"],
        text,
        openai_api_key,
        model
    ))
    
    # Return immediate response
    return web.json_response({
        "status": "processing",
        "text": text,
        "model": model
    })

async def process_synchronized_speech(tts_service, owl, text, api_key, model):
    """
    Process text with OpenAI and execute speech with synchronized movements.
    In this natural implementation, movements precede speech.
    """
    try:
        # Step 1: Analyze with OpenAI
        logger.info(f"Analyzing text with OpenAI: {text[:50]}...")
        result = await analyze_with_openai(text, api_key, model)
        
        if not result:
            logger.warning("Failed to get valid result from OpenAI")
            # Fallback to regular TTS
            tts_service.play_text(text)
            return
        
        # Step 2: Extract segments
        movements = result.get("movements", [])
        text_segments = result.get("text_segments", [])
        
        # Validate segments
        if not text_segments or not movements:
            logger.warning("Missing segments in OpenAI response")
            # Fallback to regular TTS
            tts_service.play_text(text)
            return
            
        logger.info(f"Received {len(movements)} movements and {len(text_segments)} text segments")
        
        # Step 3: Execute movement-speech pairs
        # Ensure equal length for pairing
        pair_count = min(len(movements), len(text_segments))
        
        for i in range(pair_count):
            # First execute movement (non-blocking)
            movement = movements[i]
            if isinstance(movement, dict) and "type" in movement:
                move_type = movement.get("type")
                
                # Start the movement
                await execute_movement(owl, move_type)
                
                # Immediately start speech (no pause)
                text_segment = text_segments[i].strip()
                if text_segment:
                    logger.info(f"Speaking: {text_segment[:50]}...")
                    tts_service.play_text(text_segment)
                
                # Removed: await asyncio.sleep(remaining_wait)
            else:
                logger.warning(f"Invalid movement format: {movement}")
        
        # Handle any remaining text segments if there are more text than movements
        for i in range(pair_count, len(text_segments)):
            text_segment = text_segments[i].strip()
            if text_segment:
                logger.info(f"Speaking remaining segment: {text_segment[:50]}...")
                tts_service.play_text(text_segment)
        
        logger.info("Finished synchronized speech execution")
        
    except Exception as e:
        logger.error(f"Error in synchronized speech processing: {e}", exc_info=True)
        # Fallback to regular TTS
        try:
            tts_service.play_text(text)
        except Exception as e2:
            logger.error(f"Error in fallback TTS: {e2}")
