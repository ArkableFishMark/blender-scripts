import bpy
import os
import re

def clean_asset_name(s):
    """
    Recursively strips Blender's numerical duplicate suffixes (.001) and 
    standard texture extensions to isolate the true core name of the asset.
    Example: 'PWW_00_Cloak_0173_n.dds.001' -> 'pww_00_cloak_0173_n'
    """
    if not s:
        return ""
    s = os.path.basename(s).lower()
    
    while True:
        base, ext = os.path.splitext(s)
        if not ext:
            break
        # Strip Blender duplicate markers (.001, .002, etc.)
        if re.match(r'^\.\d+$', ext):
            s = base
            continue
        # Strip standard texture extensions
        if ext in {'.png', '.jpg', '.jpeg', '.dds', '.tga', '.tif', '.tiff', '.bmp'}:
            s = base
            continue
        break
    return s

def is_target_suffix(node, suffix):
    """Case and suffix-insulated check if the node or its image matches a specific map suffix."""
    suffix = suffix.lower()
    if clean_asset_name(node.name).endswith(suffix):
        return True
    if getattr(node, 'image', None):
        if clean_asset_name(node.image.name).endswith(suffix):
            return True
        if clean_asset_name(node.image.filepath).endswith(suffix):
            return True
    return False

def is_target_contains(node, substring):
    """Case and suffix-insulated substring validation check across names and paths."""
    substring = substring.lower()
    if substring in clean_asset_name(node.name):
        return True
    if getattr(node, 'image', None):
        if substring in clean_asset_name(node.image.name):
            return True
        if substring in clean_asset_name(node.image.filepath):
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

def has_normal_map_setup(node):
    """Check if the normal texture node is already connected to a Normal Map node."""
    if 'Color' in node.outputs:
        for link in node.outputs['Color'].links:
            if link.to_node.type == 'NORMAL_MAP':
                return True
    return False

def configure_base_color_alpha(mat, bsdf):
    """Sets Base Color texture to Channel Packed and routes its Alpha output directly to the BSDF Alpha input."""
    base_color_input = bsdf.inputs.get('Base Color')
    if base_color_input and base_color_input.is_linked:
        from_node = base_color_input.links[0].from_node
        if from_node.type == 'TEX_IMAGE' and from_node.image:
            if from_node.image.alpha_mode != 'CHANNEL_PACKED':
                from_node.image.alpha_mode = 'CHANNEL_PACKED'
            
            alpha_input = bsdf.inputs.get('Alpha')
            if alpha_input and not alpha_input.is_linked:
                if 'Alpha' in from_node.outputs:
                    mat.node_tree.links.new(from_node.outputs['Alpha'], alpha_input)

def auto_load_textures_from_dir(mat, base_node):
    """Scans the Base Color texture directory for matching maps and safely imports them without duplication."""
    if not base_node.image or not base_node.image.filepath:
        return
        
    nodes = mat.node_tree.nodes
    bx, by = base_node.location
    
    filepath = bpy.path.abspath(base_node.image.filepath)
    dir_path = os.path.dirname(filepath)
    if not os.path.exists(dir_path):
        return
        
    # Sanitize our base node reference name
    base_name_clean = clean_asset_name(filepath)
    
    diffuse_suffixes = ['_hair', '_d', '_diff', '_col', '_color', '_albedo', '_basecolor', '_base', '_c', '_diffuse']
    root_name = base_name_clean
    for s in diffuse_suffixes:
        if base_name_clean.endswith(s):
            root_name = base_name_clean[:-len(s)]
            break
            
    valid_extensions = {'.png', '.jpg', '.jpeg', '.dds', '.tga', '.tif', '.tiff', '.bmp'}
    
    for filename in os.listdir(dir_path):
        f_name_clean = clean_asset_name(filename)
        
        # Ensure it contains a valid file extension somewhere in the string structure
        has_valid_ext = any(ext in filename.lower() for ext in valid_extensions)
        if not has_valid_ext:
            continue
            
        target_suffix = None
        
        if f_name_clean.endswith('_n') and (root_name in f_name_clean or base_name_clean in f_name_clean):
            target_suffix = '_n'
        elif f_name_clean.endswith('_sp') and (root_name in f_name_clean or base_name_clean in f_name_clean):
            target_suffix = '_sp'
        elif 'hairspecshift' in f_name_clean and (root_name in f_name_clean or root_name.split('_')[0] in f_name_clean):
            target_suffix = 'hairspecshift'
            
        if not target_suffix:
            continue
            
        full_path = os.path.join(dir_path, filename)
        
        # --- Multi-Layered Idempotency Check ---
        already_loaded = False
        current_scan_path = os.path.normpath(bpy.path.abspath(full_path)).lower()
        
        for n in nodes:
            if n.type == 'TEX_IMAGE' and n.image and n.image.filepath:
                existing_node_path = os.path.normpath(bpy.path.abspath(n.image.filepath)).lower()
                # 1. Path Match
                if existing_node_path == current_scan_path:
                    already_loaded = True
                    break
                # 2. Parsed Clean Name Match (catches pre-existing .001 nodes)
                if clean_asset_name(n.image.name) == f_name_clean:
                    already_loaded = True
                    break
                    
        if not already_loaded:
            try:
                img = bpy.data.images.load(full_path)
                new_node = nodes.new(type='ShaderNodeTexImage')
                new_node.image = img
                new_node.name = img.name 
                
                if target_suffix == '_n':
                    new_node.location = (bx, by - 320)
                elif target_suffix == '_sp':
                    new_node.location = (bx, by - 640)
                elif target_suffix == 'hairspecshift':
                    new_node.location = (bx - 350, by - 640)
                    
            except Exception as e:
                print(f"Failed to auto-load texture map {filename}: {e}")

def setup_materials_in_hierarchy(start_obj):
    # 1. Collect all objects in the hierarchy
    objects = [start_obj]
    for obj in objects:
        objects.extend(obj.children)
        
    # 2. Collect unique node-based materials
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
        
        # Find the Principled BSDF node
        bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not bsdf:
            continue
            
        # Process the Base Color node's Alpha Mode and auto-link Alpha channel
        configure_base_color_alpha(mat, bsdf)
        
        # Locate Base Color node and dynamically ingest maps from directory
        base_color_input = bsdf.inputs.get('Base Color')
        if base_color_input and base_color_input.is_linked:
            from_node = base_color_input.links[0].from_node
            if from_node.type == 'TEX_IMAGE':
                auto_load_textures_from_dir(mat, from_node)
            
        # Main Processing Loop
        for node in list(nodes): 
            if node.type == 'TEX_IMAGE':
                if getattr(node, 'interpolation', None) == 'Linear':
                    node.interpolation = 'Cubic'
                
                is_n = is_target_suffix(node, '_n')
                is_sp = is_target_suffix(node, '_sp')
                is_hair_spec = is_target_contains(node, 'hairspecshift')
                is_hair_base = is_target_contains(node, 'hair') and not is_hair_spec
                
                # --- Apply Utility Map Settings (Non-Color Data) ---
                if is_n or is_sp or is_hair_spec:
                    node.interpolation = 'Cubic' 
                    if node.image:
                        node.image.colorspace_settings.name = 'Non-Color'
                
                # --- Apply Normal Map Setup Logic ---
                if is_n:
                    if not has_normal_map_setup(node):
                        x, y = node.location
                        nm_node = nodes.new(type="ShaderNodeNormalMap")
                        nm_node.location = (x + 300, y)
                        
                        if bpy.app.version >= (5, 0, 0) and hasattr(nm_node, 'convention'):
                            nm_node.convention = 'DIRECTX'
                            
                        links.new(node.outputs['Color'], nm_node.inputs['Color'])
                        
                        if 'Normal' in bsdf.inputs:
                            normal_input = bsdf.inputs['Normal']
                            if normal_input.is_linked:
                                target_node = normal_input.links[0].from_node
                                if target_node.type == 'BUMP' and 'Normal' in target_node.inputs:
                                    links.new(nm_node.outputs['Normal'], target_node.inputs['Normal'])
                            else:
                                links.new(nm_node.outputs['Normal'], normal_input)
                        
                # --- Apply Channel Splitting Logic (_sp or hairspecshift) ---
                if is_sp or is_hair_spec:
                    if 'Specular Tint' in bsdf.inputs:
                        bsdf.inputs['Specular Tint'].default_value = (0.33, 0.33, 0.33, 1.0)
                        
                    if has_separate_color_setup(node):
                        continue 
                        
                    x, y = node.location
                    
                    sep_color = nodes.new(type="ShaderNodeSeparateColor")
                    sep_color.location = (x + 300, y)
                    links.new(node.outputs['Color'], sep_color.inputs['Color'])
                    
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
                        
                    spec_input = bsdf.inputs.get('Specular IOR Level') or bsdf.inputs.get('Specular')
                    if spec_input:
                        links.new(sep_color.outputs['Green'], spec_input)
                        
                    if 'Metallic' in bsdf.inputs:
                        links.new(sep_color.outputs['Blue'], bsdf.inputs['Metallic'])

                # --- Apply Hair Base Color Pseudo-Bump Logic ---
                if is_hair_base:
                    if has_bump_setup(node):
                        continue 
                    
                    x, y = node.location
                    bump_node = nodes.new(type="ShaderNodeBump")
                    bump_node.location = (x + 300, y - 250)
                    bump_node.inputs['Distance'].default_value = 0.0075
                    
                    if 'Alpha' in node.outputs:
                        links.new(node.outputs['Alpha'], bump_node.inputs['Height'])
                        
                    if 'Normal' in bsdf.inputs:
                        normal_input = bsdf.inputs['Normal']
                        if normal_input.is_linked:
                            target_node = normal_input.links[0].from_node
                            if target_node.type == 'NORMAL_MAP':
                                links.new(target_node.outputs['Normal'], bump_node.inputs['Normal'])
                                links.new(bump_node.outputs['Normal'], normal_input)
                        else:
                            links.new(bump_node.outputs['Normal'], normal_input)
            
            # --- Blender 5.0+ Global DirectX Enforcement for Normal Maps ---
            if node.type == 'NORMAL_MAP' and bpy.app.version >= (5, 0, 0):
                if hasattr(node, 'convention'):
                    if node.convention != 'DIRECTX':
                        node.convention = 'DIRECTX'

# Execute the script
if bpy.context.active_object:
    setup_materials_in_hierarchy(bpy.context.active_object)
    print("Hierarchy cleanup finalized! Block duplicates safely filtered out.")
else:
    print("Warning: Please select an active object as the root of the hierarchy.")
