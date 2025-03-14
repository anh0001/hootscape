from aiohttp import web
import asyncio
import logging
import re
import os
from robot.owl_controller import OwlController  # use the existing class
from config.settings import settings  # Import settings

logger = logging.getLogger(__name__)

# New helper function to execute a sequence of movements
async def execute_movement_sequence(owl, movements):
    loop = asyncio.get_running_loop()
    movement_map = {
        1: owl.tilt_front,
        2: owl.tilt_back,
        3: owl.rotate_right,
        4: owl.rotate_left,
        5: owl.tilt_right,
        6: owl.tilt_left,
    }
    for move in movements:
        move_type = move.get("type")
        duration = move.get("duration", 1)
        move_func = movement_map.get(move_type)
        if move_func:
            await loop.run_in_executor(None, move_func)
            await asyncio.sleep(duration)
        else:
            print(f"Invalid movement type: {move_type}")

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

async def analyze_with_openai(text):
    """
    Send text to OpenAI to analyze and add movement markers.
    """
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        if not api_key:
            logger.warning("OpenAI API key not found, returning original text")
            return text
            
        client = OpenAI(api_key=api_key)
        
        model = settings.movement_analysis_model if hasattr(settings, 'movement_analysis_model') else "gpt-3.5-turbo"
        
        prompt = f"""
        Analyze the following text and add appropriate owl movement markers.
        Use these markers: [TLTFRONT,duration], [TLTBACK,duration], [ROTRIGHT,duration], 
        [ROTLEFT,duration], [TLTRIGHT,duration], [TLTLEFT,duration].
        
        Text: {text}
        
        Return the text with movement markers inserted at natural speaking points.
        The movements should enhance the emotional content and emphasis of the speech.
        """
        
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": "You add owl movement markers to text based on emotional content and natural pauses."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error analyzing text with OpenAI: {e}")
        return text  # Return original text if analysis fails

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
    if final_text:
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
            # Add a small pause to let speech start
            await asyncio.sleep(0.3)
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
                # Execute movement
                await loop.run_in_executor(None, move_func)
                await asyncio.sleep(movement["duration"])

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
    Handle requests for synchronized speech with movements.
    """
    data = await request.json()
    text = data.get("text", "")
    
    if not text:
        return web.Response(text="No text provided", status=400)
    
    # Check if synchronized movements are enabled
    enable_sync = getattr(settings, 'enable_synchronized_movements', True)
    
    if not enable_sync:
        # If disabled, just use regular TTS
        logger.info("Synchronized movements disabled, using regular TTS")
        await request.app["event_bus"].publish("text_received", text)
        return web.json_response({"status": "fallback_to_tts", "text": text})
    
    try:
        # Call OpenAI to analyze text and add movement markers
        annotated_text = await analyze_with_openai(text)
        
        # Parse the annotated text and create a sequence of speech and movement actions
        sequence = parse_annotated_text(annotated_text)
        
        # Execute the sequence
        asyncio.create_task(execute_speech_movement_sequence(
            request.app["tts_service"], 
            request.app["owl"], 
            sequence
        ))
        
        return web.json_response({"status": "executed", "text": text})
    except Exception as e:
        logger.error(f"Error in synchronized speech: {e}")
        # Fall back to regular TTS if there's an error
        await request.app["event_bus"].publish("text_received", text)
        return web.json_response({"status": "error_fallback_to_tts", "text": text, "error": str(e)})
