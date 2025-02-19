# HootScape 🦉

An interactive, immersive soundscape experience combining ambient forest audio, an interactive owl robot, and voice integration system.

## Overview

HootScape creates a unique, multi-sensory interactive experience that blurs the lines between physical installation and digital storytelling. Running on Ubuntu 22.04, it combines spatial audio, robotics, and voice interaction to create an engaging forest environment.

### Key Features

- **Immersive Soundscape**: Spatialized forest ambience and dynamic owl sounds
- **Interactive Robot**: Physical owl that responds to player actions
- **Voice Integration**: Natural language interaction system
- **Event-Driven Architecture**: Modular design for seamless component interaction

## Requirements

### Hardware
- Intel NUC (or equivalent) running Ubuntu 22.04
- Bluetooth speaker for audio output
- USB microphone for voice input
- Owl robot (custom hardware)

### Software Dependencies
- Python 3.10+
- SpatialScaper (`pip install spatialscaper`)
- Pipecat (`pip install pipecat`)
- Additional Python packages (see `requirements.txt`)

## Installation

1. Clone the repository
2. Create and activate a virtual environment:

```bash
# Ensure Python and venv support are installed
sudo apt update
sudo apt install python3-venv python3-pip -y

# Create and activate a virtual environment
python3 -m venv hootscape-env
source hootscape-env/bin/activate

# Upgrade pip and install the core package
pip install --upgrade pip
pip install pipecat-ai

# For additional AI services (e.g. OpenAI, Deepgram)
pip install "pipecat-ai[openai,deepgram]"

# Copy the environment template and adjust as needed
mv dot-env.template .env
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up audio assets:
```bash
# Create necessary directories
mkdir -p audio/assets/forest audio/assets/owls

# Add your audio files to the respective directories:
# - audio/assets/forest/ (ambient sounds)
# - audio/assets/owls/ (owl sound effects)
```

## Project Structure

```
hootscape/
├── main.py                 # Main entry point
├── config/                 # Configuration files
├── core/                   # Core system components
├── audio/                  # Audio and soundscape management
├── robot/                  # Robot control system
├── voice/                  # Voice recognition and synthesis
└── utils/                 # Utility functions
```

## Configuration

1. Update `config/settings.py` with your specific hardware settings:
```python
# Example configuration
AUDIO_SETTINGS = {
    'sample_rate': 44100,
    'channels': 2,
    'buffer_size': 1024
}

ROBOT_SETTINGS = {
    'port': '/dev/ttyUSB0',
    'baud_rate': 115200
}
```

2. Adjust room dimensions and audio parameters in `audio/soundscape.py`:
```python
ROOM_DIMENSIONS = [5.0, 4.0, 3.0]  # Width, length, height in meters
SOURCE_RANGE = [0.5, 4.5]          # Min/max source positions
```

## Usage

1. Start the system:
```bash
python main.py
```

2. The system will:
   - Initialize the soundscape with forest ambience
   - Start the voice recognition system
   - Begin listening for participant interaction

3. Voice Commands:
   - "Hey Owl" (wake word)
   - "Where should I look?"
   - "Give me a hint"
   - "Is the baby owl nearby?"

## Development

### Adding New Features

1. **New Sound Effects**:
   - Add audio files to `audio/assets/`
   - Register them in `audio/soundscape.py`

2. **Voice Commands**:
   - Add new command handlers in `voice/commands/handlers.py`
   - Update the NLP model in `voice/recognition.py`

3. **Robot Behaviors**:
   - Add new animations in `robot/behaviors/animations.py`
   - Register them in `robot/owl_controller.py`

### Event System

The system uses an event-driven architecture. New events can be added in `config/events.py`:

```python
# Example event registration
EVENT_TYPES = {
    'GAME_START': 'game_start',
    'OWL_FOUND': 'owl_found',
    'HINT_REQUESTED': 'hint_requested'
}
```

## Troubleshooting

### Common Issues

1. **Audio Not Playing**:
   - Check Bluetooth speaker connection
   - Verify audio file paths in `audio/assets/`
   - Check system audio settings

2. **Voice Recognition Issues**:
   - Test microphone input levels
   - Verify wake word model is loaded
   - Check speech recognition configuration

3. **Robot Not Responding**:
   - Verify USB connection
   - Check robot power supply
   - Confirm serial port settings

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [SpatialScaper](https://github.com/iranroman/SpatialScaper) for spatial audio processing
- [Pipecat](https://github.com/pipecat-ai/pipecat) for voice integration
- All contributors and testers
