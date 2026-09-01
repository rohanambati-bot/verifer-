"""
Generate standard PNG icons for the Chrome Extension using Pillow.
"""
import os
from PIL import Image, ImageDraw, ImageFont


def generate_icons():
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extension", "icons")
    os.makedirs(icons_dir, exist_ok=True)

    sizes = [16, 48, 128]
    bg_color = (99, 102, 241)  # Indigo
    eye_color = (255, 255, 255)

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw rounded background circle
        draw.ellipse([1, 1, size - 2, size - 2], fill=bg_color)

        # Draw simple stylized eye shape
        center_x, center_y = size // 2, size // 2
        w, h = int(size * 0.35), int(size * 0.22)
        draw.ellipse(
            [center_x - w, center_y - h, center_x + w, center_y + h],
            fill=eye_color
        )
        # Pupil
        pupil_r = max(2, int(size * 0.12))
        draw.ellipse(
            [center_x - pupil_r, center_y - pupil_r, center_x + pupil_r, center_y + pupil_r],
            fill=(30, 27, 75)
        )

        icon_path = os.path.join(icons_dir, f"icon-{size}.png")
        img.save(icon_path, "PNG")
        print(f"Generated {icon_path} ({size}x{size})")


if __name__ == "__main__":
    generate_icons()
