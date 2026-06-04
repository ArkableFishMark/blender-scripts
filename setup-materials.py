import bpy

def is_target_suffix(node, suffix):
    """Case-insensitive check if the node name or its loaded image base-name ends with the suffix."""
    suffix = suffix.lower()
    if node.name.lower().endswith(suffix):
        return True
    if getattr(node, 'image', None):
        base_name = node.image.name.rsplit('.', 1)[0].lower()
        if base_name.endswith(suffix):
            return True
    return False

def is_target_contains(node, substring):
    """Case-insensitive check if the node name or its loaded image name contains a specific substring."""
    substring = substring.lower()
    if substring in node.name.lower():
        return True
    if getattr(node, 'image', None):
        if substring in node.image.name.lower():
            return True
    return False

def has_separate_color_setup(node):
    """Check if the texture node is already connected to a Separate Color node."""
    if 'Color' in node.outputs:
        for link in node.outputs['Color'].links:
            if link.to_node.type in {'SEPARATE_COLOR', 'SEPRGB'}:
                return True
    return False

def has_bump_setup(node):
    """Check if the texture node's Alpha output is already connected to a Bump node."""
    if 'Alpha' in node.outputs:
        for link in node.outputs['Alpha'].links:
            if link.to_node.type == 'BUMP':
                return True
    return False

def configure_base_color_alpha(bsdf):
    """Finds the Image Texture node plugged into the Base Color input and sets its alpha mode to Channel Packed."""
    base_color_input = bsdf.inputs.get('Base Color')
    if base_color_input and base_color_input.is_linked:
        # Trace back to the node connected directly to the Base Color socket
        from_node = base_color_input.links[0].from_node
        if from_node.type == 'TEX_IMAGE' and from_node.image:
            if from_node.image.alpha_mode != 'CHANNEL_PACKED':
                from_node.image.alpha_mode = 'CHANNEL_PACKED'

def setup_materials_in_hierarchy(start_obj):
    # 1. Collect all objects in the hierarchy
    objects = [start_obj]
    for obj in objects:
        objects.extend(obj.children)
        
    # 2. Collect unique node-based materials from those objects
    materials = set()
    for obj in objects:
        if obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
            for slot in obj.material_slots:
                if slot.material and slot.material.use_nodes:
                    materials.add(slot.material)
                    
    # 3. Process each material
    for mat in materials:
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Find the Principled BSDF node to attach things to
        bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not bsdf:
            continue # Skip materials without a Principled BSDF
            
        # --- NEW: Process the Base Color node's Alpha Mode ---
        configure_base_color_alpha(bsdf)
            
        for node in nodes:
            # --- Process Image Textures ---
            if node.type == 'TEX_IMAGE':
                # Convert any Linear interpolation to Cubic globally
                if getattr(node, 'interpolation', None) == 'Linear':
                    node.interpolation = 'Cubic'
                
                is_n = is_target_suffix(node, '_n')
                is_sp = is_target_suffix(node, '_sp')
                is_hair_spec = is_target_contains(node, 'hairspecshift')
                # Target textures containing "hair" but NOT the spec shift texture
                is_hair_base = is_target_contains(node, 'hair') and not is_hair_spec
                
                # --- Apply Utility Map Settings (Non-Color Data) ---
                if is_n or is_sp or is_hair_spec:
                    node.interpolation = 'Cubic' 
                    if node.image:
                        node.image.colorspace_settings.name = 'Non-Color'
                        
                # --- Apply Channel Splitting Logic (_sp or hairspecshift) ---
                if is_sp or is_hair_spec:
                    if has_separate_color_setup(node):
                        continue # Skip building if setup already exists
                        
                    x, y = node.location
                    
                    # 1. Add Separate Color node
                    sep_color = nodes.new(type="ShaderNodeSeparateColor")
                    sep_color.location = (x + 300, y)
                    links.new(node.outputs['Color'], sep_color.inputs['Color'])
                    
                    # 2. Handle Red channel routing based on texture case
                    if is_sp:
                        bc_node = nodes.new(type="ShaderNodeBrightContrast")
                        bc_node.location = (x + 500, y + 100)
                        bc_node.inputs['Contrast'].default_value = -1.0
                        
                        links.new(sep_color.outputs['Red'], bc_node.inputs['Color'])
                        if 'Roughness' in bsdf.inputs:
                            links.new(bc_node.outputs['Color'], bsdf.inputs['Roughness'])
                            
                    elif is_hair_spec:
                        if 'Roughness' in bsdf.inputs:
                            links.new(sep_color.outputs['Red'], bsdf.inputs['Roughness'])
                        
                    # 3. Connect Green -> Specular IOR Level (or Specular)
                    spec_input = bsdf.inputs.get('Specular IOR Level') or bsdf.inputs.get('Specular')
                    if spec_input:
                        links.new(sep_color.outputs['Green'], spec_input)
                        
                    # 4. Connect Blue -> Metallic
                    if 'Metallic' in bsdf.inputs:
                        links.new(sep_color.outputs['Blue'], bsdf.inputs['Metallic'])

                # --- Apply Hair Base Color Pseudo-Bump Logic ---
                if is_hair_base:
                    if has_bump_setup(node):
                        continue # Skip building if bump setup already exists
                    
                    x, y = node.location
                    
                    # 1. Add Bump node
                    bump_node = nodes.new(type="ShaderNodeBump")
                    bump_node.location = (x + 300, y - 250)
                    bump_node.inputs['Distance'].default_value = 0.0075
                    
                    # 2. Connect Alpha output to Bump Height input
                    if 'Alpha' in node.outputs:
                        links.new(node.outputs['Alpha'], bump_node.inputs['Height'])
                        
                    # 3. Connect Bump Normal output to Principled BSDF Normal input
                    if 'Normal' in bsdf.inputs:
                        links.new(bump_node.outputs['Normal'], bsdf.inputs['Normal'])
            
            # --- Blender 5.0+ DirectX for Normal Maps ---
            if node.type == 'NORMAL_MAP' and bpy.app.version >= (5, 0, 0):
                if hasattr(node, 'convention'):
                    if node.convention != 'DIRECTX':
                        node.convention = 'DIRECTX'

# Execute the script
if bpy.context.active_object:
    setup_materials_in_hierarchy(bpy.context.active_object)
    print("Successfully processed materials for the hierarchy!")
else:
    print("Warning: Please select an active object as the root of the hierarchy.")
