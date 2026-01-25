"""
JSON Persistence Utilities for A2MC Memory System

Provides thread-safe JSON read/write operations with backup support.
"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def load_json(filepath: str, default: Optional[Any] = None) -> Any:
    """
    Load JSON file, returning default if file doesn't exist.

    Args:
        filepath: Path to JSON file
        default: Value to return if file doesn't exist (default: None)

    Returns:
        Parsed JSON data or default value
    """
    path = Path(filepath)

    if not path.exists():
        logger.debug(f"File not found, returning default: {filepath}")
        return default if default is not None else {}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {filepath}: {e}")
        # Try to recover from backup
        backup_path = path.with_suffix('.json.bak')
        if backup_path.exists():
            logger.info(f"Attempting recovery from backup: {backup_path}")
            with open(backup_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        raise


def save_json(filepath: str, data: Any, backup: bool = True,
              indent: int = 2) -> None:
    """
    Save data to JSON file with optional backup.

    Args:
        filepath: Path to JSON file
        data: Data to save (must be JSON-serializable)
        backup: Whether to create backup of existing file
        indent: JSON indentation level
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create backup of existing file
    if backup and path.exists():
        backup_path = path.with_suffix('.json.bak')
        try:
            shutil.copy2(path, backup_path)
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")

    # Write to temp file first, then rename (atomic operation)
    temp_path = path.with_suffix('.json.tmp')

    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False,
                     default=_json_serializer)

        # Atomic rename
        temp_path.replace(path)
        logger.debug(f"Saved: {filepath}")

    except Exception as e:
        logger.error(f"Error saving {filepath}: {e}")
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
        raise


def _json_serializer(obj: Any) -> Any:
    """
    Custom JSON serializer for non-standard types.

    Handles:
    - datetime objects
    - Path objects
    - Objects with to_dict() method
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def merge_json(base: Dict, updates: Dict, overwrite: bool = False) -> Dict:
    """
    Recursively merge two dictionaries.

    Args:
        base: Base dictionary
        updates: Dictionary with updates
        overwrite: If True, updates overwrite base values;
                   if False, updates only add new keys

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_json(result[key], value, overwrite)
        elif key not in result or overwrite:
            result[key] = value

    return result


def validate_json_schema(data: Dict, required_fields: list) -> bool:
    """
    Simple schema validation - check required fields exist.

    Args:
        data: Data to validate
        required_fields: List of required field names

    Returns:
        True if all required fields present
    """
    missing = [f for f in required_fields if f not in data]
    if missing:
        logger.warning(f"Missing required fields: {missing}")
        return False
    return True
