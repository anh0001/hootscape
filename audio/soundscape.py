# audio/soundscape.py
import os
import numpy as np
import soundfile as sf
import time
import threading
import logging
from openal import al, alc
from ctypes import c_float, c_uint, c_int, pointer, POINTER

logger = logging.getLogger("soundscape")

class SoundscapeManager:
    def __init__(self, event_bus, assets_path='audio/assets'):
        self.event_bus = event_bus
        self.assets_path = assets_path
        
        # Initialize thread reference early to avoid potential AttributeError
        self.update_thread = None
        self.running = False
        
        # Room dimensions in meters
        self.room_dimensions = [5.0, 4.0, 3.0]
        
        # Range of possible source positions
        self.source_range = [0.5, 4.5]
        
        # Sample rate
        self.sample_rate = 44100
        
        # Initialize OpenAL
        self._initialize_openal()
        
        # Load sound assets
        self.load_sound_assets()
        
        # For managing sound source IDs
        self.sources = {}
        self.buffers = {}
        self.playing_sources = set()
        
    def _initialize_openal(self):
        """Initialize OpenAL context"""
        try:
            self.device = alc.alcOpenDevice(None)
            if not self.device:
                logger.error("Failed to open audio device")
                raise RuntimeError("Failed to open audio device")
                
            self.context = alc.alcCreateContext(self.device, None)
            if not alc.alcMakeContextCurrent(self.context):
                logger.error("Failed to create audio context")
                raise RuntimeError("Failed to create audio context")
                
            # Set distance model for realistic sound attenuation
            al.alDistanceModel(al.AL_INVERSE_DISTANCE_CLAMPED)
            
            # Set listener position (center of the room)
            al.alListener3f(al.AL_POSITION, 
                            self.room_dimensions[0]/2, 
                            self.room_dimensions[1]/2, 
                            self.room_dimensions[2]/2)
            
            # Set listener orientation (facing forward -Z axis, up +Y axis)
            orientation = [0.0, 0.0, -1.0,  # Forward vector (looking into -Z)
                           0.0, 1.0, 0.0]   # Up vector (+Y)
            # Use c_float instead of al.ALfloat
            al.alListenerfv(al.AL_ORIENTATION, (c_float * 6)(*orientation))
            
            logger.info("OpenAL initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OpenAL: {e}")
            raise
    
    def load_sound_assets(self):
        """Load sound assets from the assets directory"""
        self.forest_sounds = {}
        self.owl_sounds = {}
        
        # Load forest ambient sounds
        forest_path = os.path.join(self.assets_path, 'forest')
        if (os.path.exists(forest_path)):
            for sound_file in os.listdir(forest_path):
                if sound_file.endswith(('.wav', '.ogg', '.mp3')):
                    name = os.path.splitext(sound_file)[0]
                    self.forest_sounds[name] = os.path.join(forest_path, sound_file)
        else:
            logger.warning(f"Forest sounds directory not found: {forest_path}")
            
        # Load owl sound effects
        owls_path = os.path.join(self.assets_path, 'owls')
        if (os.path.exists(owls_path)):
            for sound_file in os.listdir(owls_path):
                if sound_file.endswith(('.wav', '.ogg', '.mp3')):
                    name = os.path.splitext(sound_file)[0]
                    self.owl_sounds[name] = os.path.join(owls_path, sound_file)
        else:
            logger.warning(f"Owl sounds directory not found: {owls_path}")
            
        logger.info(f"Loaded {len(self.forest_sounds)} forest sounds and {len(self.owl_sounds)} owl sounds")
    
    def _create_buffer(self, sound_file):
        """Create an OpenAL buffer from a sound file"""
        if sound_file in self.buffers:
            return self.buffers[sound_file]
        
        try:
            # Read audio file
            try:
                data, sample_rate = sf.read(sound_file, dtype='float32')
            except Exception as e:
                logger.error(f"Error reading sound file {sound_file}: {e}")
                logger.info(f"Attempting to use alternative method to load {sound_file}")
                # Here you could implement alternative loading methods
                # For now we'll just fail gracefully
                return None
            
            # Convert to mono if stereo
            if len(data.shape) > 1 and data.shape[1] > 1:
                data = data.mean(axis=1)
            
            # Convert to appropriate format for OpenAL
            data = (data * 32767).astype(np.int16)
            
            # Create buffer - properly using output parameter
            buffer_id = c_uint(0)
            al.alGenBuffers(1, pointer(buffer_id))
            
            # Determine format (only mono for spatial audio)
            al_format = al.AL_FORMAT_MONO16
            
            # Fill buffer with audio data
            al.alBufferData(buffer_id.value, al_format, data.tobytes(), 
                          data.nbytes, sample_rate)
            
            # Store buffer ID
            self.buffers[sound_file] = buffer_id.value
            return buffer_id.value
            
        except Exception as e:
            logger.error(f"Error creating buffer for {sound_file}: {e}")
            return None
    
    def _create_source(self, buffer_id, position, gain=1.0, pitch=1.0, loop=False):
        """Create an OpenAL source"""
        try:
            # Generate source - properly using output parameter
            source_id = c_uint(0)
            al.alGenSources(1, pointer(source_id))
            
            # Set source properties
            al.alSourcei(source_id.value, al.AL_BUFFER, buffer_id)
            al.alSourcef(source_id.value, al.AL_GAIN, gain)
            al.alSourcef(source_id.value, al.AL_PITCH, pitch)
            al.alSourcei(source_id.value, al.AL_LOOPING, al.AL_TRUE if loop else al.AL_FALSE)
            
            # Set position
            al.alSource3f(source_id.value, al.AL_POSITION, *position)
            
            # Set distance properties
            al.alSourcef(source_id.value, al.AL_REFERENCE_DISTANCE, 1.0)
            al.alSourcef(source_id.value, al.AL_MAX_DISTANCE, 10.0)
            al.alSourcef(source_id.value, al.AL_ROLLOFF_FACTOR, 1.0)
            
            return source_id.value
            
        except Exception as e:
            logger.error(f"Error creating source: {e}")
            return None
    
    def play_sound(self, sound_file, position, gain=1.0, pitch=1.0, loop=False):
        """Play a sound from a file at a specific position"""
        try:
            # Create buffer if needed
            buffer_id = self._create_buffer(sound_file)
            if buffer_id is None:
                return None
            
            # Create source
            source_id = self._create_source(buffer_id, position, gain, pitch, loop)
            if source_id is None:
                return None
            
            # Play source
            al.alSourcePlay(source_id)
            
            # Track playing source
            self.sources[source_id] = sound_file
            if loop:
                self.playing_sources.add(source_id)
            
            return source_id
            
        except Exception as e:
            logger.error(f"Error playing sound {sound_file}: {e}")
            return None
    
    def stop_sound(self, source_id):
        """Stop a playing sound"""
        if source_id is None:
            return
            
        try:
            al.alSourceStop(source_id)
            self.playing_sources.discard(source_id)
            del self.sources[source_id]
            al.alDeleteSources(1, [source_id])
        except Exception as e:
            logger.error(f"Error stopping sound {source_id}: {e}")
    
    def update_source_position(self, source_id, position):
        """Update the position of a sound source"""
        if source_id is None:
            return
            
        try:
            al.alSource3f(source_id, al.AL_POSITION, *position)
        except Exception as e:
            logger.error(f"Error updating source position {source_id}: {e}")
    
    def update_listener_position(self, position):
        """Update the position of the listener"""
        try:
            al.alListener3f(al.AL_POSITION, *position)
        except Exception as e:
            logger.error(f"Error updating listener position: {e}")
    
    def start_update_thread(self):
        """Start a thread for updating positions and managing sources"""
        if self.running:
            return
            
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def _update_loop(self):
        """Update loop for managing sources"""
        while self.running:
            # Check source states and clean up stopped sources
            sources_to_remove = []
            for source_id in list(self.sources.keys()):
                if source_id not in self.playing_sources:
                    state = c_int(0)  # Changed from c_uint to c_int
                    al.alGetSourcei(source_id, al.AL_SOURCE_STATE, pointer(state))
                    if state.value != al.AL_PLAYING:
                        sources_to_remove.append(source_id)
            
            # Clean up sources
            for source_id in sources_to_remove:
                try:
                    del self.sources[source_id]
                    source_id_c = c_uint(source_id)
                    al.alDeleteSources(1, pointer(source_id_c))
                except Exception as e:
                    logger.error(f"Error cleaning up source: {e}")
                    pass
            
            time.sleep(0.1)
    
    def stop_update_thread(self):
        """Stop the update thread"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1.0)
            self.update_thread = None
    
    def cleanup(self):
        """Clean up OpenAL resources"""
        # Stop all sources
        for source_id in list(self.sources.keys()):
            try:
                al.alSourceStop(source_id)
                source_id_c = c_uint(source_id)
                al.alDeleteSources(1, pointer(source_id_c))
            except Exception as e:
                logger.error(f"Error deleting source: {e}")
                pass
        self.sources.clear()
        self.playing_sources.clear()
        
        # Delete all buffers
        for buffer_id in list(self.buffers.values()):
            try:
                buffer_id_c = c_uint(buffer_id)
                al.alDeleteBuffers(1, pointer(buffer_id_c))
            except Exception as e:
                logger.error(f"Error deleting buffer: {e}")
                pass
        self.buffers.clear()
        
        # Destroy context
        if hasattr(self, 'context') and self.context:
            alc.alcDestroyContext(self.context)
            self.context = None
        
        # Close device
        if hasattr(self, 'device') and self.device:
            alc.alcCloseDevice(self.device)
            self.device = None
    
    async def create_forest_ambience(self):
        """Creates spatialized forest ambience"""
        source_ids = []
        
        # Add birds sound
        if 'birds' in self.forest_sounds:
            bird_pos = [self.room_dimensions[0]/2, self.room_dimensions[1]/2, self.room_dimensions[2]-0.5]
            source_id = self.play_sound(
                self.forest_sounds['birds'],
                position=bird_pos,
                gain=0.4,  # Quieter
                pitch=1.0,
                loop=True
            )
            if source_id:
                source_ids.append(source_id)
        
        # Add wind sound
        if 'wind' in self.forest_sounds:
            wind_pos = [self.room_dimensions[0]/4, self.room_dimensions[1]/2, self.room_dimensions[2]/2]
            source_id = self.play_sound(
                self.forest_sounds['wind'],
                position=wind_pos,
                gain=0.3,  # Even quieter
                pitch=0.9,  # Slightly lower
                loop=True
            )
            if source_id:
                source_ids.append(source_id)
        
        # Start update thread if not already running
        self.start_update_thread()
        
        return source_ids
    
    async def play_mother_owl_sound(self, position=None):
        """Plays spatialized mother owl sound"""
        if position is None:
            position = [2.0, 3.0, 2.0]
            
        if 'mother_call' in self.owl_sounds:
            source_id = self.play_sound(
                self.owl_sounds['mother_call'],
                position=position,
                gain=0.8,  # Louder than ambient
                pitch=1.0,
                loop=False
            )
            return source_id
        
        return None
    
    def __del__(self):
        """Destructor to ensure proper cleanup"""
        try:
            if hasattr(self, 'running') and self.running:
                self.stop_update_thread()
            if hasattr(self, 'context') or hasattr(self, 'device'):
                self.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")