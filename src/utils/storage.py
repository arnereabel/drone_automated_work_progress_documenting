"""
Photo Storage Management for Drone Photography System.

Handles organized storage of captured photos with consistent
naming conventions and directory structure.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .logger import get_logger


class StorageManager:
    """
    Manages photo storage with organized directory structure.
    
    Directory structure:
        {output_dir}/{date}/{structure_id}/stop{N}_{angle}.jpg
        
    Example:
        photos/2026-01-03/STRUCTURE_A1/stop1_front.jpg
        photos/2026-01-03/STRUCTURE_A1/stop1_left45.jpg
        photos/2026-01-03/UNKNOWN_STOP2/stop2_front.jpg
    """
    
    def __init__(self, output_directory: str = "./photos"):
        """
        Initialize storage manager.
        
        Args:
            output_directory: Base directory for photo storage.
        """
        self.output_directory = Path(output_directory)
        self.logger = get_logger("StorageManager")
        
        # Ensure output directory exists
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        # Track current session
        self._session_date = datetime.now().strftime("%Y-%m-%d")
        self._captured_photos: List[Path] = []
    
    def get_photo_path(
        self,
        structure_id: str,
        stop_number: int,
        angle_name: str,
        extension: str = "jpg",
    ) -> Path:
        """
        Generate the full path for a photo.
        
        Args:
            structure_id: Structure identifier from QR code (or "UNKNOWN").
            stop_number: Waypoint/stop number (1-indexed).
            angle_name: Name of the angle (e.g., "front", "left45").
            extension: File extension.
            
        Returns:
            Full path where the photo should be saved.
        """
        # Sanitize structure_id for filesystem
        safe_structure_id = self._sanitize_filename(structure_id)
        
        # If structure is unknown, append stop number for clarity
        if structure_id.upper() == "UNKNOWN":
            safe_structure_id = f"UNKNOWN_STOP{stop_number}"
        
        # Build path
        photo_dir = self.output_directory / self._session_date / safe_structure_id
        photo_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"stop{stop_number}_{angle_name}.{extension}"
        return photo_dir / filename
    
    def save_photo(
        self,
        image_data: bytes,
        structure_id: str,
        stop_number: int,
        angle_name: str,
    ) -> Path:
        """
        Save photo data to the appropriate location.
        
        Args:
            image_data: Raw image bytes (e.g., from cv2.imencode).
            structure_id: Structure identifier from QR code.
            stop_number: Waypoint/stop number.
            angle_name: Name of the angle.
            
        Returns:
            Path where the photo was saved.
        """
        photo_path = self.get_photo_path(structure_id, stop_number, angle_name)
        
        with open(photo_path, 'wb') as f:
            f.write(image_data)
        
        self._captured_photos.append(photo_path)
        self.logger.info(f"Saved photo: {photo_path}")
        
        return photo_path
    
    def save_frame(
        self,
        frame,  # numpy array from cv2
        structure_id: str,
        stop_number: int,
        angle_name: str,
        quality: int = 95,
    ) -> Path:
        """
        Save a cv2 frame (numpy array) as a photo.
        
        Args:
            frame: OpenCV frame (numpy array).
            structure_id: Structure identifier from QR code.
            stop_number: Waypoint/stop number.
            angle_name: Name of the angle.
            quality: JPEG quality (0-100).
            
        Returns:
            Path where the photo was saved.
        """
        import cv2
        
        photo_path = self.get_photo_path(structure_id, stop_number, angle_name)
        
        # Encode and save
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        success, encoded = cv2.imencode('.jpg', frame, encode_params)
        
        if success:
            with open(photo_path, 'wb') as f:
                f.write(encoded.tobytes())
            
            self._captured_photos.append(photo_path)
            self.logger.info(f"Saved frame: {photo_path}")
        else:
            self.logger.error(f"Failed to encode frame for: {photo_path}")
            raise IOError(f"Failed to encode frame: {photo_path}")
        
        return photo_path
    
    def get_session_photos(self) -> List[Path]:
        """
        Get all photos captured in the current session.
        
        Returns:
            List of photo paths captured since initialization.
        """
        return self._captured_photos.copy()
    
    def get_session_summary(self) -> dict:
        """
        Get summary of current session.
        
        Returns:
            Dictionary with session statistics.
        """
        return {
            "date": self._session_date,
            "total_photos": len(self._captured_photos),
            "output_directory": str(self.output_directory),
            "photos": [str(p) for p in self._captured_photos],
        }
    
    def list_dates(self) -> List[str]:
        """
        List all dates with captured photos.
        
        Returns:
            List of date strings (YYYY-MM-DD format).
        """
        dates = []
        for item in self.output_directory.iterdir():
            if item.is_dir() and self._is_date_format(item.name):
                dates.append(item.name)
        return sorted(dates, reverse=True)
    
    def list_structures(self, date: Optional[str] = None) -> List[str]:
        """
        List all structure IDs for a given date.
        
        Args:
            date: Date string (YYYY-MM-DD). Defaults to current session date.
            
        Returns:
            List of structure IDs.
        """
        if date is None:
            date = self._session_date
        
        date_dir = self.output_directory / date
        if not date_dir.exists():
            return []
        
        return [
            item.name for item in date_dir.iterdir() 
            if item.is_dir()
        ]
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string for use as filename/directory name.
        
        Args:
            name: Input string.
            
        Returns:
            Sanitized string safe for filesystem.
        """
        # Replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = name
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        return sanitized.strip()
    
    def _is_date_format(self, name: str) -> bool:
        """Check if string matches YYYY-MM-DD format."""
        try:
            datetime.strptime(name, "%Y-%m-%d")
            return True
        except ValueError:
            return False
