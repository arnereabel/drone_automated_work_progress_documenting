"""
Configuration Management for Drone Photography System.

Loads and validates configuration from YAML files.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import yaml


@dataclass
class FlightConfig:
    """Flight-related configuration."""
    takeoff_height_cm: int = 100
    movement_speed: int = 50
    hover_stability_delay_sec: float = 2.0


@dataclass
class PhotoAngle:
    """Single photo angle definition."""
    name: str
    rotation: int  # degrees, negative = left, positive = right


@dataclass
class PhotoConfig:
    """Photography configuration."""
    angles: List[PhotoAngle] = field(default_factory=list)
    delay_between_shots_sec: float = 1.0
    output_directory: str = "./photos"
    
    def __post_init__(self):
        if not self.angles:
            # Default angles: front, left 45°, right 45°
            self.angles = [
                PhotoAngle("front", 0),
                PhotoAngle("left45", -45),
                PhotoAngle("right45", 45),
            ]


@dataclass
class DetectionConfig:
    """QR detection configuration."""
    qr_timeout_sec: float = 3.0
    fallback_id: str = "UNKNOWN"


@dataclass
class SafetyConfig:
    """Safety module configuration."""
    obstacle_check_enabled: bool = True
    obstacle_threshold: float = 0.3
    gesture_confidence_threshold: float = 0.7
    emergency_gesture: str = "crossed_arms"
    gesture_check_interval_sec: float = 0.5


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: str = "./logs/mission.log"
    console: bool = True


@dataclass
class Waypoint:
    """Single waypoint definition."""
    name: str
    x: int  # cm, relative to takeoff
    y: int  # cm
    z: int  # cm (height)
    description: str = ""


@dataclass 
class WaypointsConfig:
    """Waypoints configuration."""
    waypoints: List[Waypoint] = field(default_factory=list)
    return_home: bool = True
    navigation_speed: Optional[int] = None


@dataclass
class MissionConfig:
    """Complete mission configuration."""
    flight: FlightConfig = field(default_factory=FlightConfig)
    photo: PhotoConfig = field(default_factory=PhotoConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    waypoints_config: WaypointsConfig = field(default_factory=WaypointsConfig)


class ConfigManager:
    """
    Manages loading and accessing configuration.
    
    Usage:
        config = ConfigManager()
        config.load_mission("config/mission_default.yaml")
        config.load_waypoints("config/waypoints_mvp.yaml")
        
        print(config.mission.flight.takeoff_height_cm)
        print(config.waypoints)
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            base_path: Base path for relative config paths. 
                       Defaults to project root.
        """
        if base_path is None:
            # Default to project root (parent of src/)
            self.base_path = Path(__file__).parent.parent
        else:
            self.base_path = Path(base_path)
        
        self.mission = MissionConfig()
        self._raw_mission: Dict[str, Any] = {}
        self._raw_waypoints: Dict[str, Any] = {}
    
    def load_mission(self, config_path: str) -> MissionConfig:
        """
        Load mission configuration from YAML file.
        
        Args:
            config_path: Path to mission config YAML file.
            
        Returns:
            Loaded MissionConfig object.
        """
        full_path = self._resolve_path(config_path)
        
        with open(full_path, 'r') as f:
            self._raw_mission = yaml.safe_load(f)
        
        self._parse_mission_config()
        return self.mission
    
    def load_waypoints(self, config_path: str) -> List[Waypoint]:
        """
        Load waypoints configuration from YAML file.
        
        Args:
            config_path: Path to waypoints config YAML file.
            
        Returns:
            List of Waypoint objects.
        """
        full_path = self._resolve_path(config_path)
        
        with open(full_path, 'r') as f:
            self._raw_waypoints = yaml.safe_load(f)
        
        self._parse_waypoints_config()
        return self.waypoints
    
    @property
    def waypoints(self) -> List[Waypoint]:
        """Get list of waypoints."""
        return self.mission.waypoints_config.waypoints
    
    @property
    def return_home(self) -> bool:
        """Check if drone should return home after mission."""
        return self.mission.waypoints_config.return_home
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base path if not absolute."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p
    
    def _parse_mission_config(self) -> None:
        """Parse raw mission dict into dataclasses."""
        raw = self._raw_mission
        
        # Flight config
        if 'flight' in raw:
            self.mission.flight = FlightConfig(**raw['flight'])
        
        # Photo config
        if 'photo' in raw:
            photo_raw = raw['photo'].copy()
            if 'angles' in photo_raw:
                photo_raw['angles'] = [
                    PhotoAngle(**a) for a in photo_raw['angles']
                ]
            self.mission.photo = PhotoConfig(**photo_raw)
        
        # Detection config
        if 'detection' in raw:
            self.mission.detection = DetectionConfig(**raw['detection'])
        
        # Safety config
        if 'safety' in raw:
            self.mission.safety = SafetyConfig(**raw['safety'])
        
        # Logging config
        if 'logging' in raw:
            self.mission.logging = LoggingConfig(**raw['logging'])
    
    def _parse_waypoints_config(self) -> None:
        """Parse raw waypoints dict into dataclasses."""
        raw = self._raw_waypoints
        
        waypoints = []
        for wp_raw in raw.get('waypoints', []):
            waypoints.append(Waypoint(
                name=wp_raw.get('name', 'Unnamed'),
                x=wp_raw.get('x', 0),
                y=wp_raw.get('y', 0),
                z=wp_raw.get('z', 100),
                description=wp_raw.get('description', ''),
            ))
        
        self.mission.waypoints_config = WaypointsConfig(
            waypoints=waypoints,
            return_home=raw.get('return_home', True),
            navigation_speed=raw.get('navigation_speed'),
        )
    
    def get_output_directory(self) -> Path:
        """Get resolved photo output directory path."""
        output_dir = self._resolve_path(self.mission.photo.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def get_log_file_path(self) -> Path:
        """Get resolved log file path."""
        log_path = self._resolve_path(self.mission.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path


# Convenience function for quick loading
def load_config(
    mission_path: str = "config/mission_default.yaml",
    waypoints_path: str = "config/waypoints_mvp.yaml",
    base_path: Optional[str] = None,
) -> ConfigManager:
    """
    Convenience function to load both mission and waypoints config.
    
    Args:
        mission_path: Path to mission config YAML.
        waypoints_path: Path to waypoints config YAML.
        base_path: Base path for resolving relative paths.
        
    Returns:
        Configured ConfigManager instance.
    """
    config = ConfigManager(base_path)
    config.load_mission(mission_path)
    config.load_waypoints(waypoints_path)
    return config
