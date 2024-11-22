import bpy
import re
from mathutils import Vector


def fix_bone_lengths():
    """Fix bones with lengths less than 1 unit by adding 2.5 units."""
    armature = bpy.context.active_object
    
    if not armature or armature.type != 'ARMATURE':
        print("Please select an armature")
        return
    
    # Switch to edit mode to modify bone properties
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    fixed_bones = []
    
    for bone in edit_bones:
        current_length = (bone.tail - bone.head).length
        
        if current_length < 1.0:
            head_pos = bone.head.copy()
            
            if current_length > 0:
                # Maintain direction but add 2.5 to length
                direction = (bone.tail - bone.head).normalized()
                new_length = current_length + 2.5
                bone.tail = head_pos + (direction * new_length)
            else:
                # Default vertical direction for zero-length bones
                direction = Vector((0.0, 0.0, 1.0))
                
                if bone.parent:
                    parent_dir = (bone.parent.tail - bone.parent.head).normalized()
                    if parent_dir.length > 0:
                        direction = parent_dir
                
                bone.tail = head_pos + (direction * 2.5)
                new_length = 2.5
            
            fixed_bones.append((bone.name, current_length, 
                              (bone.tail - bone.head).length))
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    if fixed_bones:
        print("\nFixed bone lengths:")
        for bone_name, old_length, new_length in fixed_bones:
            print(f"- {bone_name}: {old_length:.3f}m → {new_length:.3f}m")
    else:
        print("No bones with length < 1m found")


def rename_special_eye_bones():
    """Rename special eye bones according to predefined mapping."""
    armature = bpy.context.active_object
    
    eye_bone_mapping = {
        'B_eye_left_right': 'B_eye_inner_left',
        'B_eye_left_left': 'B_eye_outer_left',
        'B_eye_right_right': 'B_eye_outer_right',
        'B_eye_right_left': 'B_eye_inner_right'
    }
    
    for bone in armature.data.bones:
        if bone.name in eye_bone_mapping:
            new_name = eye_bone_mapping[bone.name]
            bone.name = new_name
            print(f"Special rename: {bone.name} → {new_name}")


def rename_bones():
    """Rename bones according to standardized patterns."""
    armature = bpy.context.active_object
    
    if not armature or armature.type != 'ARMATURE':
        print("Please select an armature")
        return
    
    rename_special_eye_bones()
    
    patterns = [
        (r'^(.*?)_(R|L)_(.*)$', 
         lambda m: f"{m.group(1)}_{m.group(3)} {m.group(2)}"),
        (r'^(.*?)_(L|R)([A-Z].*)$', 
         lambda m: f"{m.group(1)}_{m.group(3)} {m.group(2)}"),
        (r'^(.+?)_(?:right|left)_(.+)$', 
         lambda m: f"{m.group(1)}_{m.group(2)} {'R' if 'right' in m.group(0) else 'L'}"),
        (r'^(.+?)_(?:right|left)([a-z][^_]*)$', 
         lambda m: f"{m.group(1)}_{m.group(2)} {'R' if 'right' in m.group(0) else 'L'}")
    ]
    
    for bone in armature.data.bones:
        original_name = bone.name
        new_name = original_name
        
        for pattern, formatter in patterns:
            match = re.match(pattern, original_name)
            if match:
                new_name = formatter(match)
                break
        
        if new_name != original_name:
            bone.name = new_name
            print(f"Renamed: {original_name} → {new_name}")


def symmetrize_bones():
    """Symmetrize left side bones to right side."""
    armature = bpy.context.active_object
    
    if not armature or armature.type != 'ARMATURE':
        print("Please select an armature")
        return
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.armature.select_all(action='DESELECT')
    
    edit_bones = armature.data.edit_bones
    
    # Select all left side bones
    for bone in edit_bones:
        if bone.name.endswith(' L') or '_left' in bone.name.lower():
            bone.select = True
            bone.select_head = True
            bone.select_tail = True
    
    # Set active bone for symmetrize operation
    for bone in edit_bones:
        if bone.select:
            armature.data.edit_bones.active = bone
            break
    
    bpy.ops.armature.symmetrize(direction='NEGATIVE_X')
    bpy.ops.object.mode_set(mode='OBJECT')
    print("Symmetrize operation completed")


def main():
    """Execute bone operations in correct order."""
    fix_bone_lengths()
    rename_bones()
    symmetrize_bones()


if __name__ == "__main__":
    main()