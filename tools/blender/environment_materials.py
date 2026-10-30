"""Original packed palette and standalone shader authoring (no scene settings)."""
import bpy

from rr.core.environment_geometry import PALETTE


def rgba(hex_color: str) -> tuple[float, ...]:
    return tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.,)


def toon() -> bpy.types.Material:
    """Palette lookup multiplied by two normal-based lighting bands.

    Fixed art-directed light direction avoids renderer-specific ShaderToRGB.
    VERIFY appearance in UPBGE; this is a portable authoring material.
    """
    image = bpy.data.images.new("T_P0Palette_BC", width=512, height=512, alpha=False)
    row = [channel for color in PALETTE for _ in range(32) for channel in rgba(color)]
    image.pixels = row * 512
    image.file_format = "PNG"
    image.pack()
    material = bpy.data.materials.new("MT_ToonBase")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    texture = nodes.new("ShaderNodeTexImage")
    texture.image, texture.interpolation = image, "Closest"
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "PaletteUV"
    links.new(uv.outputs["UV"], texture.inputs["Vector"])
    normal = nodes.new("ShaderNodeNewGeometry")
    dot = nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = (.35, -.45, .82)
    links.new(normal.outputs["Normal"], dot.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (.55, .55, .55, 1)
    ramp.color_ramp.elements[1].position = .2
    links.new(dot.outputs["Value"], ramp.inputs[0])
    multiply = nodes.new("ShaderNodeMixRGB")
    multiply.blend_type = "MULTIPLY"
    multiply.inputs[0].default_value = 1
    links.new(texture.outputs["Color"], multiply.inputs[1])
    links.new(ramp.outputs["Color"], multiply.inputs[2])
    emission = nodes.new("ShaderNodeEmission")
    links.new(multiply.outputs[0], emission.inputs["Color"])
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs[0], output.inputs["Surface"])
    return material


def sky() -> bpy.types.World:
    """Own-made horizon-to-zenith gradient; never assigned to a scene."""
    world = bpy.data.worlds.new("EN_SkyDay")
    world.use_nodes, world.use_fake_user = True, True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    coordinate = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coordinate.outputs["Normal"], separate.inputs[0])
    height = nodes.new("ShaderNodeMath")
    height.operation = "MULTIPLY"
    height.inputs[1].default_value = -1
    links.new(separate.outputs["Z"], height.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = rgba("FFE4BA")
    ramp.color_ramp.elements[1].color = rgba("4E9FC9")
    links.new(height.outputs[0], ramp.inputs[0])
    background = nodes.new("ShaderNodeBackground")
    links.new(ramp.outputs[0], background.inputs["Color"])
    output = nodes.new("ShaderNodeOutputWorld")
    links.new(background.outputs[0], output.inputs["Surface"])
    world["VERIFY"] = "Manual appearance and runtime world integration; no scene assignment"
    return world
