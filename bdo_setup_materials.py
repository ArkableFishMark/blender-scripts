import bpy
import os
import re

def clean_asset_name(s):
    if not s: 
        return ""
    s = os.path.basename(s).lower()
    while True:
        base, ext = os.path.splitext(s)
        if not ext: 
            break
        if re.match(r'^\.\d+$', ext): 
            s = base
            continue
        if ext in {'.png', '.jpg', '.jpeg', '.dds', '.tga', '.tif', '.tiff', '.bmp'}: 
            s = base
            continue
        break
    return s

def is_target_suffix(node, suffix):
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
    if 'Color' in node.outputs:
        for link in node.outputs['Color'].links:
            if link.to_node.type in {'SEPARATE_COLOR', 'SEPRGB'}: 
                return True
    return False

def has_bump_setup(node):
    if 'Alpha' in node.outputs:
        for link in node.outputs['Alpha'].links:
            if link.to_node.type == 'BUMP': 
                return True
    return False

def has_normal_map_setup(node):
    if 'Color' in node.outputs:
        for link in node.outputs['Color'].links:
            if link.to_node.type == 'NORMAL_MAP': 
                return True
    return False

def get_upstream_tex_node(start_socket):
    if not start_socket or not start_socket.is_linked:
        return None
    nodes_to_check = [start_socket.links[0].from_node]
    checked_nodes = set()
    
    while nodes_to_check:
        current_node = nodes_to_check.pop(0)
        if current_node in checked_nodes:
            continue
        checked_nodes.add(current_node)
        if current_node.type == 'TEX_IMAGE':
            return current_node
        for node_input in current_node.inputs:
            if node_input.is_linked:
                nodes_to_check.append(node_input.links[0].from_node)
    return None

def configure_base_color_alpha(mat, bsdf):
    base_color_input = bsdf.inputs.get('Base Color')
    source_tex_node = get_upstream_tex_node(base_color_input)
    
    if source_tex_node and source_tex_node.image:
        if source_tex_node.image.alpha_mode != 'CHANNEL_PACKED':
            source_tex_node.image.alpha_mode = 'CHANNEL_PACKED'
        alpha_input = bsdf.inputs.get('Alpha')
        if alpha_input and not alpha_input.is_linked:
            if 'Alpha' in source_tex_node.outputs:
                mat.node_tree.links.new(source_tex_node.outputs['Alpha'], alpha_input)

def auto_load_textures_from_dir(mat, base_node):
    if not base_node or not base_node.image or not base_node.image.filepath: 
        return
        
    nodes = mat.node_tree.nodes
    bx, by = base_node.location
    filepath = bpy.path.abspath(base_node.image.filepath)
    dir_path = os.path.dirname(filepath)
    
    if not os.path.exists(dir_path): 
        return
        
    base_name_clean = clean_asset_name(filepath)
    # Removed '_hair' from this list so it is treated as part of the unique root name
    diffuse_suffixes = ['_d', '_diff', '_col', '_color', '_albedo', '_basecolor', '_base', '_c', '_diffuse']
    root_name = base_name_clean
    for s in diffuse_suffixes:
        if base_name_clean.endswith(s):
            root_name = base_name_clean[:-len(s)]
            break
            
    valid_extensions = {'.png', '.jpg', '.jpeg', '.dds', '.tga', '.tif', '.tiff', '.bmp'}
    
    for filename in os.listdir(dir_path):
        f_name_clean = clean_asset_name(filename)
        if not any(ext in filename.lower() for ext in valid_extensions): 
            continue
            
        target_suffix = None
        # Now using exact matching to prevent cross-contamination
        if f_name_clean == f"{root_name}_n":
            target_suffix = '_n'
        elif f_name_clean == f"{root_name}_sp":
            target_suffix = '_sp'
        elif f_name_clean == f"{root_name}_m":
            target_suffix = '_m'
        elif 'hairspecshift' in f_name_clean and (root_name in f_name_clean or root_name.split('_')[0] in f_name_clean):
            target_suffix = 'hairspecshift'
            
        if not target_suffix: 
            continue
            
        full_path = os.path.join(dir_path, filename)
        already_loaded = False
        current_scan_path = os.path.normpath(bpy.path.abspath(full_path)).lower()
        
        for n in nodes:
            if n.type == 'TEX_IMAGE' and n.image and n.image.filepath:
                existing_node_path = os.path.normpath(bpy.path.abspath(n.image.filepath)).lower()
                if existing_node_path == current_scan_path or clean_asset_name(n.image.name) == f_name_clean:
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
                elif target_suffix == '_m':
                    new_node.location = (bx, by + 320)
                elif target_suffix == 'hairspecshift': 
                    new_node.location = (bx - 350, by - 640)
            except Exception as e:
                print(f"Failed to auto-load texture map {filename}: {e}")

def process_single_material(mat):
    if not mat or not mat.use_nodes: 
        return
        
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    
    if not bsdf: 
        return
        
    configure_base_color_alpha(mat, bsdf)
    
    base_color_input = bsdf.inputs.get('Base Color')
    source_tex_node = get_upstream_tex_node(base_color_input)
    if source_tex_node:
        auto_load_textures_from_dir(mat, source_tex_node)
        
    for node in list(nodes): 
        if node.type == 'TEX_IMAGE':
            if getattr(node, 'interpolation', None) == 'Linear': 
                node.interpolation = 'Cubic'
            
            is_n = is_target_suffix(node, '_n')
            is_sp = is_target_suffix(node, '_sp')
            is_m = is_target_suffix(node, '_m')
            is_hair_spec = is_target_contains(node, 'hairspecshift')
            is_hair_base = is_target_contains(node, 'hair') and not is_hair_spec
            
            if is_n or is_sp or is_m or is_hair_spec:
                node.interpolation = 'Cubic' 
                if node.image: 
                    node.image.colorspace_settings.name = 'Non-Color'
            
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
            
            if is_m:
                if not has_separate_color_setup(node):
                    x, y = node.location
                    sep_color = nodes.new(type="ShaderNodeSeparateColor")
                    sep_color.location = (x + 300, y)
                    links.new(node.outputs['Color'], sep_color.inputs['Color'])
                    
                    channels = ['Red', 'Green', 'Blue']
                    for i, channel in enumerate(channels):
                        mix_node = nodes.new(type="ShaderNodeMix")
                        mix_node.data_type = 'RGBA'
                        mix_node.blend_type = 'MIX'
                        mix_node.location = (x + 550, y - (i * 200))
                        links.new(sep_color.outputs[channel], mix_node.inputs['Factor'])

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
        
        if node.type == 'NORMAL_MAP' and bpy.app.version >= (5, 0, 0):
            if hasattr(node, 'convention') and node.convention != 'DIRECTX': 
                node.convention = 'DIRECTX'

def setup_materials_in_hierarchy(start_obj, processed_materials):
    objects = [start_obj]
    for obj in objects:
        objects.extend(obj.children)
        
    for obj in objects:
        if obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
            for slot in obj.material_slots:
                if slot.material:
                    if slot.material in processed_materials: 
                        continue
                    process_single_material(slot.material)
                    processed_materials.add(slot.material)

if bpy.context.selected_objects:
    global_processed_materials = set()
    for obj in bpy.context.selected_objects:
        setup_materials_in_hierarchy(obj, global_processed_materials)
    print("Batch hierarchy processing complete!")
else:
    print("Warning: Please select at least one root object.")
