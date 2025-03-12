# core/user_profile.py
import os
import json
import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Any, Optional
import aiofiles

logger = logging.getLogger("user_profile")

class UserProfile:
    """
    Represents a single user profile with preferences and health data
    """
    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name
        self.voice_preferences = {
            "language": "en",
            "rate": 1.0,
            "pitch": 1.0,
            "volume": 0.8
        }
        self.medications = []  # List of medication objects
        self.reminders = []    # List of reminder objects  
        self.emergency_contacts = []  # List of contact objects
        self.health_metrics = {}  # Dictionary of health metric histories
        self.preferences = {
            "wake_time": "08:00",
            "sleep_time": "22:00",
            "preferred_topics": ["health", "weather", "family"]
        }
        self.interaction_history = []  # List of recent interactions
    
    def add_medication(self, name: str, dosage: str, schedule: List[str]):
        """Add a medication to the user's profile"""
        medication = {
            "id": len(self.medications) + 1,
            "name": name,
            "dosage": dosage,
            "schedule": schedule,  # List of times like ["08:00", "20:00"]
            "last_taken": None
        }
        self.medications.append(medication)
        return medication["id"]
    
    def add_reminder(self, title: str, datetime_str: str, repeat: Optional[str] = None):
        """Add a reminder to the user's profile"""
        reminder = {
            "id": len(self.reminders) + 1,
            "title": title,
            "datetime": datetime_str,
            "repeat": repeat,  # None, "daily", "weekly", etc.
            "completed": False
        }
        self.reminders.append(reminder)
        return reminder["id"]
    
    def add_emergency_contact(self, name: str, relation: str, phone: str):
        """Add an emergency contact"""
        contact = {
            "id": len(self.emergency_contacts) + 1,
            "name": name,
            "relation": relation,
            "phone": phone
        }
        self.emergency_contacts.append(contact)
        return contact["id"]
    
    def record_health_metric(self, metric_type: str, value: float, unit: str):
        """Record a health metric measurement"""
        if metric_type not in self.health_metrics:
            self.health_metrics[metric_type] = []
        
        measurement = {
            "timestamp": datetime.now().isoformat(),
            "value": value,
            "unit": unit
        }
        self.health_metrics[metric_type].append(measurement)
    
    def record_interaction(self, interaction_type: str, content: str):
        """Record an interaction with the user"""
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "type": interaction_type,
            "content": content
        }
        self.interaction_history.append(interaction)
        # Keep only the most recent 100 interactions
        if len(self.interaction_history) > 100:
            self.interaction_history = self.interaction_history[-100:]
    
    def to_dict(self):
        """Convert profile to dictionary for serialization"""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "voice_preferences": self.voice_preferences,
            "medications": self.medications,
            "reminders": self.reminders,
            "emergency_contacts": self.emergency_contacts,
            "health_metrics": self.health_metrics,
            "preferences": self.preferences,
            "interaction_history": self.interaction_history
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create profile from dictionary"""
        profile = cls(data["user_id"], data["name"])
        profile.voice_preferences = data.get("voice_preferences", profile.voice_preferences)
        profile.medications = data.get("medications", [])
        profile.reminders = data.get("reminders", [])
        profile.emergency_contacts = data.get("emergency_contacts", [])
        profile.health_metrics = data.get("health_metrics", {})
        profile.preferences = data.get("preferences", profile.preferences)
        profile.interaction_history = data.get("interaction_history", [])
        return profile

class ProfileManager:
    """
    Manages user profiles for the healthcare system.
    Provides persistence and lookup functionality.
    """
    def __init__(self, profiles_dir="data/profiles"):
        self.profiles_dir = profiles_dir
        self.profiles = {}  # Dictionary of loaded profiles
        self.active_profile_id = None
        self._ensure_dir_exists()
    
    def _ensure_dir_exists(self):
        """Ensure the profiles directory exists"""
        os.makedirs(self.profiles_dir, exist_ok=True)
    
    def get_profile_path(self, user_id):
        """Get the file path for a profile"""
        return os.path.join(self.profiles_dir, f"{user_id}.json")
    
    async def load_profile(self, user_id):
        """Load a profile from disk"""
        path = self.get_profile_path(user_id)
        
        try:
            if os.path.exists(path):
                async with aiofiles.open(path, 'r') as f:
                    data = json.loads(await f.read())
                    profile = UserProfile.from_dict(data)
                    self.profiles[user_id] = profile
                    logger.info(f"Loaded profile for user {user_id}")
                    return profile
            else:
                logger.warning(f"Profile for user {user_id} not found")
                return None
        except Exception as e:
            logger.error(f"Error loading profile for user {user_id}: {e}")
            return None
    
    async def save_profile(self, profile):
        """Save a profile to disk"""
        path = self.get_profile_path(profile.user_id)
        
        try:
            async with aiofiles.open(path, 'w') as f:
                await f.write(json.dumps(profile.to_dict(), indent=2))
            logger.info(f"Saved profile for user {profile.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving profile for user {profile.user_id}: {e}")
            return False
    
    async def create_profile(self, user_id, name):
        """Create a new profile"""
        if user_id in self.profiles:
            logger.warning(f"Profile for user {user_id} already exists")
            return self.profiles[user_id]
        
        profile = UserProfile(user_id, name)
        self.profiles[user_id] = profile
        await self.save_profile(profile)
        logger.info(f"Created new profile for user {user_id}")
        return profile
    
    def get_profile(self, user_id):
        """Get a loaded profile"""
        return self.profiles.get(user_id)
    
    async def list_profiles(self):
        """List all available profiles"""
        profiles = []
        try:
            for filename in os.listdir(self.profiles_dir):
                if filename.endswith(".json"):
                    user_id = filename[:-5]  # Remove .json extension
                    if user_id not in self.profiles:
                        # Load the profile if it's not already loaded
                        await self.load_profile(user_id)
                    profiles.append(self.profiles[user_id])
            return profiles
        except Exception as e:
            logger.error(f"Error listing profiles: {e}")
            return []
    
    def set_active_profile(self, user_id):
        """Set the active profile"""
        if user_id in self.profiles:
            self.active_profile_id = user_id
            logger.info(f"Set active profile to {user_id}")
            return True
        else:
            logger.warning(f"Cannot set active profile - user {user_id} not loaded")
            return False
    
    def get_active_profile(self):
        """Get the active profile"""
        if self.active_profile_id:
            return self.profiles.get(self.active_profile_id)
        return None
    
    async def update_profile(self, user_id, updates):
        """Update a profile with new data"""
        profile = self.get_profile(user_id)
        if not profile:
            logger.warning(f"Cannot update profile - user {user_id} not found")
            return False
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        # Save the updated profile
        await self.save_profile(profile)
        return True

# Example usage:
async def example():
    # Create a profile manager
    manager = ProfileManager()
    
    # Create a profile
    alice = await manager.create_profile("alice", "Alice Johnson")
    
    # Add some medications
    alice.add_medication("Lisinopril", "10mg", ["08:00"])
    alice.add_medication("Metformin", "500mg", ["08:00", "20:00"])
    
    # Add some reminders
    alice.add_reminder("Doctor Appointment", "2023-05-15T14:30:00", None)
    alice.add_reminder("Take Blood Pressure", "08:30", "daily")
    
    # Add emergency contacts
    alice.add_emergency_contact("Bob Johnson", "Son", "555-1234")
    alice.add_emergency_contact("Dr. Smith", "Doctor", "555-5678")
    
    # Record some health metrics
    alice.record_health_metric("blood_pressure", 120, "mmHg")
    alice.record_health_metric("blood_glucose", 110, "mg/dL")
    
    # Save the profile
    await manager.save_profile(alice)
    
    # Set as active profile
    manager.set_active_profile("alice")
    
    # Get active profile
    active = manager.get_active_profile()
    print(f"Active profile: {active.name}")

if __name__ == "__main__":
    asyncio.run(example())