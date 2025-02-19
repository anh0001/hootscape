import asyncio
from core.event_bus import EventBus
from audio.soundscape import SoundscapeManager
from voice.recognition import VoiceSystem
from robot.owl_controller import OwlRobot

async def main():
    # Initialize event bus
    event_bus = EventBus()
    
    # Initialize components
    soundscape = SoundscapeManager(event_bus)
    voice_system = VoiceSystem(event_bus)
    owl_robot = OwlRobot(event_bus)
    
    # Start voice system
    await voice_system.start()
    
    # Create initial forest ambience
    forest_audio = await soundscape.create_forest_ambience()
    # Play forest audio (implementation depends on your audio output system)
    
    try:
        while True:
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        # Cleanup
        await voice_system.stop()

if __name__ == "__main__":
    asyncio.run(main())# Placeholder for main.py