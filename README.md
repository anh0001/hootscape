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

### 1. Setup Virtual Environment
```bash
conda create --prefix hootscape-env python=3.11
conda activate ./hootscape-env
```

### 2. Install System Dependencies (Ubuntu 22.04)
```bash
sudo apt update
sudo apt install portaudio19-dev
sudo apt install ffmpeg
```

### 3. Configure Network Settings
To set a fixed IP address for the system:

```bash
# Replace YourWiFiConnectionName with your connection name
# You can find it using: nmcli connection show
sudo nmcli connection modify "YourWiFiConnectionName" \
    ipv4.addresses 192.168.1.84/24 \
    ipv4.gateway 192.168.1.1 \
    ipv4.dns "8.8.8.8 8.8.4.4" \
    ipv4.method manual

# Apply the changes
sudo nmcli connection up "YourWiFiConnectionName"
```

### 4. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
```bash
cp dot-env.template .env
```

### 5. Configure Environment Settings
Edit the `.env` file to set your HTTP server and robot parameters.

### 6. Set Up Audio Assets
```bash
mkdir -p audio/assets/forest audio/assets/owls
# Add your audio files:
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
└── utils/                  # Utility functions
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

3. The system leverages Pydantic settings to load the `.env` file. Modify key parameters in the `.env` file without touching the code.

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

## API Command Format

The system accepts commands via HTTP POST requests to `/owl/command` on port 9123. The endpoint supports several payload formats:

### 1. Speech Command

Send text-to-speech commands with optional rate and pitch parameters. Text must end with '!' for immediate processing.

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "speech": {
    "text": "Hello, HootScape!",
    "rate": 1.0,
    "pitch": 1.0
  }
}' http://localhost:9123/owl/command
```

### 2. Movement Sequence

Execute a series of movements. Movement types:
- 1: Tilt Front
- 2: Tilt Back
- 3: Rotate Right
- 4: Rotate Left
- 5: Tilt Right
- 6: Tilt Left

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "movements": [
    {"type": 5, "duration": 1},
    {"type": 6, "duration": 1},
    {"type": 5, "duration": 1}
  ]
}' http://localhost:9123/owl/command
```

### 3. Combined Speech and Movement

Combine TTS and movement commands in a single request:

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "speech": {
    "text": "Hello, HootScape!",
    "rate": 1.0,
    "pitch": 1.0
  },
  "movements": [
    {"type": 5, "duration": 1},
    {"type": 6, "duration": 1}
  ]
}' http://localhost:9123/owl/command
```

### 4. Macro Commands

Execute predefined movement sequences using named macros:

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "macro": "happy"
}' http://localhost:9123/owl/command
```

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
