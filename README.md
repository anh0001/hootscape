# HootScape Healthcare Assistant 🦉

An interactive, immersive healthcare companion combining ambient forest audio, an interactive owl robot, and voice interaction system designed specifically for elderly care in living lab environments.

## Overview

HootScape Healthcare creates a unique, multi-sensory interactive healthcare experience that blurs the lines between physical installation and digital caregiving. Running on Ubuntu 22.04, it combines spatial audio, robotics, and voice interaction to create an engaging and supportive environment for elderly users.

### Key Features

- **Immersive Soundscape**: Spatialized forest ambience and calming owl sounds to create a soothing environment
- **Interactive Robot**: Physical owl that responds to user actions with gentle, reassuring movements
- **Voice Integration**: Natural language interaction system optimized for elderly users
- **Healthcare Functionality**: Medication reminders, health monitoring, and emergency assistance
- **User Profiles**: Personalized experiences based on individual healthcare needs
- **Event-Driven Architecture**: Modular design for seamless component interaction

## Healthcare Applications

HootScape Healthcare is specially designed for elderly care in trailer living lab environments:

- **Medication Management**: Reminds users to take medications on schedule with appropriate dosages
- **Health Monitoring**: Assists with tracking vital signs and health metrics
- **Emergency Response**: Provides quick access to emergency contacts when needed
- **Social Companionship**: Reduces feelings of isolation through conversational interactions
- **Cognitive Engagement**: Offers simple activities and conversations to maintain mental acuity

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

### 5. Configure Environment Settings
```bash
cp dot-env.template .env
```
Edit the `.env` file to set your HTTP server, robot parameters, and voice service API keys.

### 6. Set Up Audio Assets
```bash
mkdir -p audio/assets/forest audio/assets/owls
# Add your audio files:
# - audio/assets/forest/ (ambient sounds in WAV format)
# - audio/assets/owls/ (owl sound effects in WAV format)
```

## Project Structure

```
hootscape/
├── main.py                     # Main entry point
├── config/                     # Configuration files
├── core/                       # Core system components
│   ├── event_bus.py           # Event management system
│   ├── state_manager.py       # Application state tracking
│   └── user_profile.py        # User profile management
├── audio/                      # Audio and soundscape management
│   ├── assets/                # Audio files (WAV format)
│   ├── soundscape.py          # Spatial audio environment
│   └── tts_service.py         # Text-to-speech service
├── robot/                      # Robot control system
│   ├── owl_controller.py      # Owl hardware interface
│   └── behaviors/             # Predefined robot behaviors
├── voice/                      # Voice recognition and synthesis
│   ├── recognition.py         # Speech-to-text processing
│   ├── synthesis.py           # Advanced TTS features
│   └── commands/              # Voice command handlers
└── utils/                      # Utility functions
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

3. Configure voice preferences for elderly users in `.env`:
```
TTS_RATE=0.9             # Slightly slower speech rate
TTS_PITCH=1.0            # Normal pitch
TTS_VOLUME=0.8           # Moderate volume
```

## Soundscape Setup

The system uses WAV audio files (not MP3) stored in specific directories:

1. Create ambient sounds in `audio/assets/forest/`:
   - Nature sounds like birds, wind, rain, etc.
   - Recommended format: 44.1kHz, 16-bit WAV files
   - Keep files under 30 seconds for better memory usage

2. Add owl sounds in `audio/assets/owls/`:
   - Various owl calls and responses
   - Same technical specifications as above

The SpatialScaper library creates a 3D audio environment from these files, placing sounds at different virtual positions to create an immersive experience.

## User Profiles

HootScape Healthcare stores user profiles in `data/profiles/` as JSON files:

```bash
mkdir -p data/profiles
```

Each profile contains:
- Personal information
- Medication schedules
- Health metric history
- Emergency contacts
- Voice and interaction preferences

## Usage

1. Start the system:
```bash
python main.py
```

2. The system will:
   - Initialize the soundscape with forest ambience
   - Start the voice recognition system
   - Begin listening for "Hey Owl" wake word
   - Load user profiles if available

3. Healthcare Voice Commands:
   - "Hey Owl, remind me to take my medication"
   - "Hey Owl, check my blood pressure"
   - "Hey Owl, call my caregiver"
   - "Hey Owl, let's talk for a while"

## API Command Format

The system accepts commands via HTTP POST requests to `/owl/command` on port 9123. The endpoint supports several payload formats:

### 1. Speech Command

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "speech": {
    "text": "It's time to take your medication.",
    "rate": 0.9,
    "pitch": 1.0
  }
}' http://localhost:9123/owl/command
```

### 2. Movement Sequence

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "movements": [
    {"type": 5, "duration": 1},
    {"type": 6, "duration": 1},
    {"type": 5, "duration": 1}
  ]
}' http://localhost:9123/owl/command
```

### 3. Combined Healthcare Command

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "speech": {
    "text": "Don't forget to drink water with your medication.",
    "rate": 0.9,
    "pitch": 1.0
  },
  "movements": [
    {"type": 1, "duration": 1},
    {"type": 3, "duration": 1}
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

## Elderly User Considerations

- **Voice Recognition**: Optimize for older voices that may be softer or less distinct
- **Speech Output**: Use slightly slower speech rate with clear enunciation
- **Visual Feedback**: Ensure owl movements are gentle and non-startling
- **Command Simplicity**: Keep voice commands simple and natural
- **Consistency**: Maintain consistent interaction patterns

## Acknowledgments

- [SpatialScaper](https://github.com/iranroman/SpatialScaper) for spatial audio processing
- [Pipecat](https://github.com/pipecat-ai/pipecat) for voice integration
- All contributors and testers