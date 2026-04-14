#!/usr/bin/env python3
"""Generate PM-OS app icon SVG with pixel-art sine wave dithering."""

import math

# === Main icon (512x512, icon area 56,56 to 456,456) ===

BG_COLOR = "#001122"
PINK = "#ff0088"
PIXEL = 12
ICON_X = 56
ICON_Y = 56
ICON_W = 400
ICON_H = 400

# 4x4 Bayer dithering matrix (normalized to 0-1)
BAYER_4x4 = [
    [0/16, 8/16, 2/16, 10/16],
    [12/16, 4/16, 14/16, 6/16],
    [3/16, 11/16, 1/16, 9/16],
    [15/16, 7/16, 13/16, 5/16],
]

def generate_main_icon():
    cols = ICON_W // PIXEL  # 33 columns
    rows = ICON_H // PIXEL  # 33 rows

    rects = []
    for row in range(rows):
        for col in range(cols):
            px = ICON_X + col * PIXEL
            py = ICON_Y + row * PIXEL
            # Center of this pixel block
            cx = px + PIXEL / 2
            cy = py + PIXEL / 2

            # Sine wave: one full period across the icon width
            # wave_y is the y-coordinate of the wave at this x position
            wave_y = ICON_Y + ICON_H / 2 + 80 * math.sin(2 * math.pi * (cx - ICON_X) / ICON_W)

            # Distance from wave: negative = above wave (should be pink), positive = below
            dist = cy - wave_y

            # Dithering zone width (in pixels)
            dither_zone = 36  # 3 pixel-blocks worth of transition

            if dist < -dither_zone:
                # Well above wave: solid pink
                rects.append((px, py, PINK))
            elif dist > dither_zone:
                # Well below wave: dark background (no rect needed, bg shows)
                pass
            else:
                # In the dithering zone: use Bayer threshold
                # Normalize distance to 0-1 (0 = top of zone/pink, 1 = bottom/dark)
                t = (dist + dither_zone) / (2 * dither_zone)
                threshold = BAYER_4x4[row % 4][col % 4]
                if t < threshold:
                    rects.append((px, py, PINK))
                # else: dark background

    # Build SVG
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">',
        '  <defs>',
        '    <clipPath id="roundedClip">',
        f'      <rect x="{ICON_X}" y="{ICON_Y}" width="{ICON_W}" height="{ICON_H}" rx="62"/>',
        '    </clipPath>',
        '  </defs>',
        '',
        '  <!-- Background with macOS-standard padding and rounded corners -->',
        f'  <rect x="{ICON_X}" y="{ICON_Y}" width="{ICON_W}" height="{ICON_H}" rx="62" fill="{BG_COLOR}"/>',
        '',
        '  <!-- Pixelated sine wave with Bayer dithering -->',
        '  <g clip-path="url(#roundedClip)">',
    ]

    for px, py, color in rects:
        lines.append(f'    <rect x="{px}" y="{py}" width="{PIXEL}" height="{PIXEL}" fill="{color}"/>')

    lines.append('  </g>')
    lines.append('</svg>')

    return '\n'.join(lines)


# === Tray icon (22x22, white on transparent) ===

def generate_tray_icon():
    size = 22
    pixel = 2  # smaller pixel blocks for 22x22
    cols = size // pixel  # 11
    rows = size // pixel  # 11
    dither_zone = 3  # smaller zone for small icon

    rects = []
    for row in range(rows):
        for col in range(cols):
            px = col * pixel
            py = row * pixel
            cx = px + pixel / 2
            cy = py + pixel / 2

            wave_y = size / 2 + (size * 0.2) * math.sin(2 * math.pi * cx / size)
            dist = cy - wave_y

            if dist < -dither_zone:
                rects.append((px, py))
            elif dist > dither_zone:
                pass
            else:
                t = (dist + dither_zone) / (2 * dither_zone)
                threshold = BAYER_4x4[row % 4][col % 4]
                if t < threshold:
                    rects.append((px, py))

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">',
    ]
    for px, py in rects:
        lines.append(f'  <rect x="{px}" y="{py}" width="{pixel}" height="{pixel}" fill="white"/>')
    lines.append('</svg>')

    return '\n'.join(lines)


if __name__ == '__main__':
    import os
    base = os.path.dirname(os.path.abspath(__file__))

    icon_svg = generate_main_icon()
    with open(os.path.join(base, 'icon-source.svg'), 'w') as f:
        f.write(icon_svg)
    print(f"Written icon-source.svg ({len(icon_svg)} bytes)")

    tray_svg = generate_tray_icon()
    with open(os.path.join(base, 'tray-icon-source.svg'), 'w') as f:
        f.write(tray_svg)
    print(f"Written tray-icon-source.svg ({len(tray_svg)} bytes)")
