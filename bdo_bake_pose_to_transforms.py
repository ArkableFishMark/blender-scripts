import bpy

def apply_armature_to_shape_keys(obj, modifier):
    """Bakes the armature deformation into the base mesh and all shape keys."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    shape_keys = obj.data.shape_keys.key_blocks
    
    # 1. Save original shape key values and modifier viewport states
    original_sk_values = {sk.name: sk.value for sk in shape_keys}
    original_mod_states = {}
    
    for mod in obj.modifiers:
        if mod != modifier:
            original_mod_states[mod.name] = mod.show_viewport
            mod.show_viewport = False  # Mute other modifiers to prevent baking them
            
    modifier.show_viewport = True
    
    # 2. Extract deformed coordinates for each shape key
    sk_coords = {}
    for sk in shape_keys:
        # Isolate the current shape key
        for key in shape_keys:
            key.value = 1.0 if key == sk else 0.0
            
        bpy.context.view_layer.update()
        
        # Evaluate object to get the deformed mesh
        eval_obj = obj.evaluated_get(depsgraph)
        temp_mesh = bpy.data.meshes.new_from_object(eval_obj)
        
        # Store the exact vertex coordinates
        sk_coords[sk.name] = [v.co.copy() for v in temp_mesh.vertices]
        
        # Clean up temporary mesh data
        bpy.data.meshes.remove(temp_mesh)
        
    # 3. Apply the extracted coordinates back to the original shape keys
    for sk in shape_keys:
        coords = sk_coords[sk.name]
        for i, co in enumerate(coords):
            sk.data[i].co = co
            
    # 4. Restore original values and modifier states
    for sk in shape_keys:
        sk.value = original_sk_values[sk.name]
        
    for mod in obj.modifiers:
        if mod.name in original_mod_states:
            mod.show_viewport = original_mod_states[mod.name]
            
    # 5. Remove the armature modifier (it is now baked in)
    obj.modifiers.remove(modifier)

def apply_pose_to_bulk():
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Identify the selected armature and meshes
    armature = next((obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE'), None)
    meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

    if not armature or not meshes:
        print("Error: Please select one Armature and at least one Mesh.")
        return

    processed_meshes = []

    # 1. Safely apply the Armature modifier (handling shape keys if present)
    for obj in meshes:
        bpy.context.view_layer.objects.active = obj
        
        armature_mod = next((mod for mod in obj.modifiers if mod.type == 'ARMATURE' and mod.object == armature), None)
        
        if armature_mod:
            if obj.data.shape_keys:
                apply_armature_to_shape_keys(obj, armature_mod)
            else:
                bpy.ops.object.modifier_apply(modifier=armature_mod.name)
            
            processed_meshes.append(obj)

    if not processed_meshes:
        print("No matching armature modifiers found on selected meshes.")
        return

    # 2. Set the current pose as the new Rest Pose
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    
    # CORRECTED LINE: Removed the invalid set_as keyword argument
    bpy.ops.pose.armature_apply() 
    
    bpy.ops.object.mode_set(mode='OBJECT')

    # 3. Re-add the Armature modifier to the processed meshes
    for obj in processed_meshes:
        existing_mod = next((mod for mod in obj.modifiers if mod.type == 'ARMATURE' and mod.object == armature), None)
        if not existing_mod:
            new_mod = obj.modifiers.new(name="Armature", type='ARMATURE')
            new_mod.object = armature

    print(f"Success: Set new rest pose and relinked {len(processed_meshes)} meshes.")

# Execute the script
apply_pose_to_bulk()
