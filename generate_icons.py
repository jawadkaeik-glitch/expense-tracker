import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_premium_app_icon(size):
    # Create high-res image with smooth dark background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background Squircle with Gradient
    bg = Image.new("RGBA", (size, size), (9, 13, 22, 255)) # #090d16
    bg_draw = ImageDraw.Draw(bg)

    # Draw rounded squircle
    radius = int(size * 0.22) # Apple/Android standard 22% squircle radius
    bg_draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=(15, 23, 42, 255)) # #0f172a

    # Add vibrant radial glow in center
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = size // 2, size // 2
    gr = int(size * 0.45)
    glow_draw.ellipse([cx - gr, cy - gr, cx + gr, cy + gr], fill=(16, 185, 129, 60)) # Emerald green glow
    glow = glow.filter(ImageFilter.GaussianBlur(int(size * 0.15)))
    bg = Image.alpha_composite(bg, glow)

    # Re-mask to squircle shape
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
    
    # 2. Draw Sleek Geometric Logo Emblem (Modern "K" + Wealth Flow Curve)
    emblem = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    e_draw = ImageDraw.Draw(emblem)

    # Scale factor for drawing
    s = size / 512.0

    # Draw Primary Emerald Bar (Vertical Stem of K)
    stem_x = int(140 * s)
    stem_w = int(54 * s)
    e_draw.rounded_rectangle([stem_x, int(110 * s), stem_x + stem_w, int(400 * s)], radius=int(20 * s), fill=(16, 185, 129, 255))

    # Draw Upper Diagonal Arm (Electric Cyan / Gold Gradient Accent)
    arm_top = [(int(200 * s), int(260 * s)), (int(340 * s), int(110 * s)), (int(400 * s), int(110 * s)), (int(240 * s), int(290 * s))]
    e_draw.polygon(arm_top, fill=(6, 182, 212, 255)) # Cyan

    # Draw Lower Diagonal Arm (Golden Wealth Arrow Accent)
    arm_bottom = [(int(220 * s), int(265 * s)), (int(370 * s), int(400 * s)), (int(315 * s), int(400 * s)), (int(175 * s), int(310 * s))]
    e_draw.polygon(arm_bottom, fill=(245, 158, 11, 255)) # Gold

    # Draw Central Electric Lightning Bolt Accent (Fused ⚡ Curve)
    lightning = [(int(260 * s), int(130 * s)), (int(210 * s), int(270 * s)), (int(275 * s), int(270 * s)), (int(225 * s), int(390 * s)), (int(310 * s), int(230 * s)), (int(245 * s), int(230 * s))]
    e_draw.polygon(lightning, fill=(251, 191, 36, 255)) # Bright Amber

    # Merge emblem onto background with mask
    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final.paste(bg, (0, 0), mask)
    final = Image.alpha_composite(final, emblem)

    # 3. Add 1px Subtle Glassmorphic Border Highlight
    border_draw = ImageDraw.Draw(final)
    border_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, outline=(255, 255, 255, 40), width=int(max(1, 2 * s)))

    return final

# Create icons
os.makedirs("c:/Users/UserPc/expense-tracker/static/icons", exist_ok=True)
icon192 = create_premium_app_icon(192)
icon192.save("c:/Users/UserPc/expense-tracker/static/icons/icon-192.png")

icon512 = create_premium_app_icon(512)
icon512.save("c:/Users/UserPc/expense-tracker/static/icons/icon-512.png")

print("Generated ultra-high-resolution premium app icons: icon-192.png and icon-512.png")
