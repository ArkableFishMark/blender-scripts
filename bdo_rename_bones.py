import bpy
import re

def rename_bones():
    # Get the active armature
    armature = bpy.context.active_object
    
    if not armature or armature.type != 'ARMATURE':
        print("Please select an armature")
        return
    
    # Patterns to match different bone naming conventions
    patterns = [
        # Pattern 1: Bip01_R_Clavicle
        (r'^(.*?)_(R|L)_(.*)$', lambda m: f"{m.group(1)}_{m.group(3)} {m.group(2)}"),
        
        # Pattern 2: Bip01_LUpArmTwist
        (r'^(.*?)_(L|R)([A-Z].*)$', lambda m: f"{m.group(1)}_{m.group(3)} {m.group(2)}"),
        
        # Pattern 3: B_eyebrow_right_up
        (r'^(.+?)_(?:right|left)_(.+)$', 
         lambda m: f"{m.group(1)}_{m.group(2)} {'R' if 'right' in m.group(0) else 'L'}"),
        
        # Pattern 4: B_laughlines_rightup
        (r'^(.+?)_(?:right|left)([a-z][^_]*)$', 
         lambda m: f"{m.group(1)}_{m.group(2)} {'R' if 'right' in m.group(0) else 'L'}")
    ]
    
    # Iterate through all bones
    for bone in armature.data.bones:
        original_name = bone.name
        new_name = original_name
        
        # Convert name to lowercase for case-insensitive matching
        lower_name = original_name.lower()
        
        # Try each pattern
        for pattern, formatter in patterns:
            match = re.match(pattern, original_name)
            if match:
                new_name = formatter(match)
                break
        
        # Rename the bone if a match was found
        if new_name != original_name:
            bone.name = new_name
            print(f"Renamed: {original_name} → {new_name}")

# Run the function
rename_bones()