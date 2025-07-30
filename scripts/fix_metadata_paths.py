#!/usr/bin/env python3
"""
Fix Windows-style paths in metadata.json to Unix-style paths for macOS/Linux compatibility
"""

import json
import sys
from pathlib import Path

def fix_metadata_paths():
    """Convert Windows backslash paths to Unix forward slash paths in metadata.json"""
    
    # Path to metadata file
    metadata_path = Path("data/pickles/metadata.json")
    
    if not metadata_path.exists():
        print(f"Error: {metadata_path} not found")
        return False
    
    try:
        # Read the metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Track changes
        changes_made = 0
        
        # Create new metadata with fixed paths
        fixed_metadata = {}
        
        for key, value in metadata.items():
            # Fix the key (file path)
            fixed_key = key.replace('\\', '/')
            
            # Fix the file_path in the value
            if 'file_path' in value:
                original_path = value['file_path']
                value['file_path'] = original_path.replace('\\', '/')
                
                if original_path != value['file_path']:
                    changes_made += 1
                    print(f"Fixed path: {original_path} -> {value['file_path']}")
            
            fixed_metadata[fixed_key] = value
        
        # Write the fixed metadata back
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_metadata, f, ensure_ascii=False, indent=2)
        
        print(f"\nSuccessfully fixed {changes_made} paths in metadata.json")
        return True
        
    except Exception as e:
        print(f"Error fixing metadata paths: {e}")
        return False

if __name__ == "__main__":
    success = fix_metadata_paths()
    sys.exit(0 if success else 1)