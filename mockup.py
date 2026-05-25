"""
2D garment mockup generator.

Renders simple flat garment silhouettes (one per garment type), colors them
the requested base color, and composites the customer's logo on top at the
specified placement and size. Not photorealistic - the goal is to confirm
"this is roughly what it will look like" before production runs.

In production this would call a service like Printful's mockup API or use
proper garment templates with UV mapping. For the demo, programmatic
PIL drawing is sufficient.
"""
from io import BytesIO
from PIL import Image, ImageDraw

# Map color names to RGB tuples. Falls back to mid-gray for unknowns.
COLOR_RGB = {
    "White": (245, 245, 245),
    "Black": (30, 30, 30),
    "Navy": (28, 39, 78),
    "Royal Blue": (35, 70, 165),
    "Carolina Blue": (123, 175, 212),
    "Light Blue": (170, 200, 225),
    "Red": (180, 30, 35),
    "Maroon": (110, 30, 40),
    "Burgundy": (110, 30, 50),
    "Forest Green": (40, 75, 50),
    "Hunter Green": (40, 70, 50),
    "Kelly Green": (60, 130, 60),
    "Sport Gray": (160, 160, 160),
    "Heather Gray": (170, 170, 170),
    "Charcoal": (60, 65, 70),
    "Gold": (210, 165, 50),
    "Athletic Gold": (220, 170, 40),
    "Orange": (220, 110, 40),
    "Purple": (90, 50, 130),
    "Pink": (230, 160, 195),
    "Hot Pink": (235, 80, 160),
    "Khaki": (180, 165, 130),
    "Stone": (190, 180, 165),
    "Natural": (225, 215, 190),
    "Yellow": (235, 210, 60),
    "Camo": (110, 115, 80),
    "Light Stone Wash": (170, 185, 210),
    "Medium Wash": (95, 120, 160),
    "Dark Indigo": (50, 70, 110),
    "Black Denim": (40, 45, 60),
    "Vintage Wash": (140, 160, 185),
}

# Canvas dimensions for mockup
CANVAS_W = 500
CANVAS_H = 600
BG_COLOR = (250, 250, 246)  # warm bg matching HDS palette


def _color_for(name):
    return COLOR_RGB.get(name, (160, 160, 160))


def _draw_tshirt(draw, fill, outline=(60, 60, 60)):
    """T-shirt silhouette. Returns chest/back placement reference rect."""
    pts = [
        (170, 130),   # left collar
        (140, 110),   # left shoulder inside
        (80, 145),    # left sleeve top
        (50, 230),    # left sleeve bottom
        (105, 245),   # left sleeve inseam
        (130, 220),   # left body start
        (130, 510),   # left hem
        (370, 510),   # right hem
        (370, 220),   # right body start
        (395, 245),   # right sleeve inseam
        (450, 230),   # right sleeve bottom
        (420, 145),   # right sleeve top
        (360, 110),   # right shoulder inside
        (330, 130),   # right collar
        (290, 145),   # collar bottom right
        (250, 150),   # collar V bottom
        (210, 145),   # collar bottom left
    ]
    draw.polygon(pts, fill=fill, outline=outline)
    draw.line([(210, 145), (250, 150), (290, 145)], fill=outline, width=2)


def _draw_polo(draw, fill, outline=(60, 60, 60)):
    """Polo: T-shirt with proper collar and placket."""
    _draw_tshirt(draw, fill, outline)
    # Collar (folded)
    collar_pts = [(205, 142), (250, 175), (295, 142), (290, 130), (250, 155), (210, 130)]
    draw.polygon(collar_pts, fill=fill, outline=outline)
    # Placket (button strip)
    draw.line([(250, 155), (250, 215)], fill=outline, width=2)
    draw.ellipse((247, 170, 253, 176), fill=outline)
    draw.ellipse((247, 190, 253, 196), fill=outline)


def _draw_hoodie(draw, fill, outline=(60, 60, 60)):
    """Hoodie: T-shirt with hood and pocket."""
    # Hood (rendered behind the body)
    hood_pts = [(170, 130), (160, 90), (200, 60), (300, 60), (340, 90), (330, 130)]
    draw.polygon(hood_pts, fill=fill, outline=outline)
    # Inside hood (darker)
    inner = tuple(max(0, c - 30) for c in fill[:3])
    draw.polygon([(190, 110), (220, 90), (280, 90), (310, 110), (300, 135), (200, 135)], fill=inner, outline=outline)
    # Body
    _draw_tshirt(draw, fill, outline)
    # Kangaroo pocket
    draw.polygon([(170, 360), (330, 360), (320, 460), (180, 460)], fill=tuple(max(0, c - 15) for c in fill[:3]), outline=outline)
    # Drawstrings
    draw.line([(225, 130), (215, 200)], fill=(240, 235, 215), width=3)
    draw.line([(275, 130), (285, 200)], fill=(240, 235, 215), width=3)


def _draw_cap(draw, fill, outline=(60, 60, 60)):
    """Baseball cap: crown + bill."""
    # Crown
    draw.pieslice((130, 200, 370, 440), 180, 360, fill=fill, outline=outline)
    # Brim/bill
    bill_color = tuple(max(0, c - 25) for c in fill[:3])
    draw.chord((100, 310, 400, 400), 180, 360, fill=bill_color, outline=outline)
    # Button on top
    draw.ellipse((245, 195, 255, 205), fill=outline)
    # Stitching detail (panels)
    draw.line([(250, 200), (250, 320)], fill=outline, width=1)
    draw.line([(180, 230), (215, 320)], fill=outline, width=1)
    draw.line([(320, 230), (285, 320)], fill=outline, width=1)


def _draw_tote(draw, fill, outline=(60, 60, 60)):
    """Canvas tote bag: rectangle body + two handle straps."""
    # Body
    draw.rectangle((130, 200, 370, 510), fill=fill, outline=outline)
    # Handles
    draw.arc((180, 100, 250, 220), 180, 360, fill=outline, width=4)
    draw.arc((250, 100, 320, 220), 180, 360, fill=outline, width=4)


def _draw_performance(draw, fill, outline=(60, 60, 60)):
    """Performance shirt: T-shirt with mesh accent panels."""
    _draw_tshirt(draw, fill, outline)
    # Side panels (slightly darker for visual interest)
    accent = tuple(max(0, c - 40) for c in fill[:3])
    draw.polygon([(130, 220), (160, 230), (160, 480), (130, 510)], fill=accent)
    draw.polygon([(370, 220), (340, 230), (340, 480), (370, 510)], fill=accent)


def _draw_denim_jacket(draw, fill, outline=(40, 40, 60)):
    """Denim jacket: T-shirt base with lapels, pockets, buttons."""
    _draw_tshirt(draw, fill, outline)
    # Lapels (folded back collar pieces)
    draw.polygon([(170, 145), (210, 145), (240, 250), (200, 280), (170, 220)], fill=tuple(max(0, c - 20) for c in fill[:3]), outline=outline)
    draw.polygon([(330, 145), (290, 145), (260, 250), (300, 280), (330, 220)], fill=tuple(max(0, c - 20) for c in fill[:3]), outline=outline)
    # Center button placket
    draw.line([(250, 200), (250, 510)], fill=outline, width=2)
    for y in (230, 280, 330, 380, 430, 480):
        draw.ellipse((245, y - 4, 255, y + 4), fill=(220, 210, 180), outline=outline)
    # Chest pockets
    draw.rectangle((155, 280, 225, 360), outline=outline, width=2)
    draw.rectangle((275, 280, 345, 360), outline=outline, width=2)


def _draw_towel(draw, fill, outline=(60, 60, 60)):
    """Towel: rectangle with terrycloth texture indication."""
    draw.rectangle((80, 150, 420, 520), fill=fill, outline=outline)
    # Hem stripes
    inner = tuple(max(0, c - 25) for c in fill[:3])
    draw.rectangle((80, 150, 420, 175), fill=inner, outline=outline)
    draw.rectangle((80, 495, 420, 520), fill=inner, outline=outline)


GARMENT_DRAWERS = {
    "T-shirt (100% cotton)": _draw_tshirt,
    "Polo shirt (cotton-poly blend)": _draw_polo,
    "Hoodie / sweatshirt (heavy fleece)": _draw_hoodie,
    "Cap / hat (structured)": _draw_cap,
    "Canvas tote bag": _draw_tote,
    "Performance / athletic (poly)": _draw_performance,
    "Denim jacket": _draw_denim_jacket,
    "Towel (terrycloth)": _draw_towel,
}


# Placement coordinates expressed as (center_x_pct, center_y_pct) on the canvas
# AND a reference scale: how many canvas pixels equal 1 inch on the garment.
# Each garment type has its own (placement -> (cx_pct, cy_pct)) map.
PLACEMENT_COORDS = {
    "T-shirt (100% cotton)": {
        "Left Chest": (0.40, 0.42),
        "Right Chest": (0.60, 0.42),
        "Center Chest": (0.50, 0.50),
        "Full Front": (0.50, 0.58),
        "Full Back": (0.50, 0.58),
        "Back Yoke (upper)": (0.50, 0.37),
        "Left Sleeve": (0.18, 0.32),
        "Right Sleeve": (0.82, 0.32),
        "pixels_per_inch": 16.0,
    },
    "Polo shirt (cotton-poly blend)": {
        "Left Chest": (0.40, 0.45),
        "Right Chest": (0.60, 0.45),
        "Left Sleeve": (0.18, 0.32),
        "Right Sleeve": (0.82, 0.32),
        "Back Yoke (upper)": (0.50, 0.40),
        "pixels_per_inch": 16.0,
    },
    "Hoodie / sweatshirt (heavy fleece)": {
        "Left Chest": (0.40, 0.42),
        "Right Chest": (0.60, 0.42),
        "Center Chest": (0.50, 0.48),
        "Full Front": (0.50, 0.55),
        "Full Back": (0.50, 0.55),
        "Hood (left)": (0.43, 0.18),
        "Left Sleeve": (0.18, 0.32),
        "Right Sleeve": (0.82, 0.32),
        "pixels_per_inch": 16.0,
    },
    "Performance / athletic (poly)": {
        "Left Chest": (0.40, 0.42),
        "Right Chest": (0.60, 0.42),
        "Center Chest": (0.50, 0.50),
        "Full Front": (0.50, 0.58),
        "Full Back": (0.50, 0.58),
        "Left Sleeve": (0.18, 0.32),
        "Right Sleeve": (0.82, 0.32),
        "pixels_per_inch": 16.0,
    },
    "Denim jacket": {
        "Left Chest": (0.36, 0.55),
        "Right Chest": (0.64, 0.55),
        "Full Back": (0.50, 0.65),
        "Left Sleeve": (0.18, 0.35),
        "Right Sleeve": (0.82, 0.35),
        "pixels_per_inch": 16.0,
    },
    "Cap / hat (structured)": {
        "Front Center": (0.50, 0.50),
        "Side Left": (0.30, 0.55),
        "Side Right": (0.70, 0.55),
        "Back": (0.50, 0.50),
        "pixels_per_inch": 22.0,  # caps are smaller so each inch is more pixels
    },
    "Canvas tote bag": {
        "Center Front": (0.50, 0.58),
        "Center Back": (0.50, 0.58),
        "pixels_per_inch": 18.0,
    },
    "Towel (terrycloth)": {
        "Corner Embroidery": (0.20, 0.78),
        "Center Hem": (0.50, 0.80),
        "pixels_per_inch": 18.0,
    },
}


def render_mockup(garment, base_color, logo_image, placement, logo_width_in, logo_height_in):
    """Composite a logo onto a flat garment silhouette.

    Args:
        garment: e.g. "T-shirt (100% cotton)"
        base_color: e.g. "Navy"
        logo_image: PIL Image of the logo (RGBA preferred)
        placement: e.g. "Left Chest"
        logo_width_in: logo width in inches
        logo_height_in: logo height in inches

    Returns:
        PIL Image (RGBA) of the mocked-up garment.
    """
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), BG_COLOR + (255,))
    draw = ImageDraw.Draw(canvas)
    fill = _color_for(base_color)

    drawer = GARMENT_DRAWERS.get(garment)
    if drawer:
        drawer(draw, fill)
    else:
        # Generic placeholder
        draw.rectangle((100, 150, 400, 510), fill=fill, outline=(60, 60, 60))

    # Place logo if we have coords for this combo
    coords = PLACEMENT_COORDS.get(garment, {})
    if placement in coords and logo_image is not None and logo_width_in and logo_height_in:
        cx_pct, cy_pct = coords[placement]
        ppi = coords.get("pixels_per_inch", 16.0)

        target_w = max(1, int(logo_width_in * ppi))
        target_h = max(1, int(logo_height_in * ppi))

        logo_rgba = logo_image.convert("RGBA")
        # Preserve aspect ratio by fitting inside target box
        logo_rgba.thumbnail((target_w, target_h), Image.LANCZOS)

        cx = int(CANVAS_W * cx_pct)
        cy = int(CANVAS_H * cy_pct)
        paste_x = cx - logo_rgba.width // 2
        paste_y = cy - logo_rgba.height // 2

        canvas.paste(logo_rgba, (paste_x, paste_y), logo_rgba)

    return canvas
