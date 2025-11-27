
import asyncio
import os
import random
import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from calendar import monthrange, month_name
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

# Mock classes
class MockUser:
    def __init__(self, user_id, name, color_code):
        self.user_id = user_id
        self.name = name
        self.color_code = color_code
        self.is_hidden = False

class MockShift:
    def __init__(self, shift_date, user_ids):
        self.date = shift_date
        self.user_ids = user_ids

# Mock data
MOCK_USERS = [
    MockUser(1, "Alice", "#FF5733"),
    MockUser(2, "Bob", "#33FF57"),
    MockUser(3, "Charlie", "#3357FF"),
    MockUser(4, "Diana", "#F333FF"),
    MockUser(5, "Eve", "#33FFF5"),
]

MOCK_SHIFTS = {}

# Populate mock shifts
today = date.today()
year = today.year
month = today.month
num_days = monthrange(year, month)[1]
for d in range(1, num_days + 1):
    current_date = date(year, month, d)
    # Random shifts
    if d % 2 == 0:
        MOCK_SHIFTS[current_date] = MockShift(current_date, [1, 2])
    elif d % 3 == 0:
        MOCK_SHIFTS[current_date] = MockShift(current_date, [3])
    else:
        MOCK_SHIFTS[current_date] = MockShift(current_date, [4, 5])

# Ukrainian constants
UKRAINIAN_MONTHS = {
    1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень",
    5: "Травень", 6: "Червень", 7: "Липень", 8: "Серпень",
    9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень",
}
UKRAINIAN_DAYS = ["П", "В", "С", "Ч", "П", "С", "Н"]

def get_month_name_ukrainian(month: int) -> str:
    return UKRAINIAN_MONTHS.get(month, month_name[month])

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

def add_noise(image: Image.Image, intensity: int = 15) -> Image.Image:
    """Add Gaussian noise to image"""
    width, height = image.size
    noise = Image.effect_noise((width, height), intensity)
    noise = noise.convert("RGB")
    
    # Blend noise with image
    if image.mode == "RGBA":
        noise = noise.convert("RGBA")
        # Make noise semi-transparent
        noise.putalpha(30)
        return Image.alpha_composite(image, noise)
    else:
        return ImageChops.blend(image, noise, 0.05)

def create_organic_blob(width: int, height: int, color: Tuple[int, int, int]) -> Image.Image:
    """Create a fuzzy organic blob"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Random blob parameters
    cx, cy = width // 2, height // 2
    radius = min(width, height) // 3
    points = []
    steps = 12
    for i in range(steps):
        angle = (i / steps) * 2 * math.pi
        r = radius * random.uniform(0.8, 1.2)
        x = cx + math.cos(angle) * r
        y = cy + math.sin(angle) * r
        points.append((x, y))
    
    # Draw polygon and blur heavily
    draw.polygon(points, fill=color + (200,))
    return img.filter(ImageFilter.GaussianBlur(radius=radius//2))

def create_mesh_gradient(width: int, height: int, colors: List[Tuple[int, int, int]]) -> Image.Image:
    """Create a complex mesh-like gradient background"""
    base = Image.new("RGB", (width, height), colors[0])
    
    # Add random blobs of other colors
    for color in colors[1:]:
        # Random position and size
        blob_w = int(width * random.uniform(0.8, 1.5))
        blob_h = int(height * random.uniform(0.8, 1.5))
        blob = create_organic_blob(blob_w, blob_h, color)
        
        # Paste at random position
        x = random.randint(-blob_w//2, width - blob_w//2)
        y = random.randint(-blob_h//2, height - blob_h//2)
        
        base.paste(blob, (x, y), blob)
    
    return base

def draw_squircle(draw, xy, radius, fill=None, outline=None, width=1):
    """Draw a superellipse (squircle) approximation"""
    x1, y1, x2, y2 = xy
    w = x2 - x1
    h = y2 - y1
    
    # Use standard rounded rect for now but with smoother corners logic if needed
    # For true squircle we'd need to draw points manually, but standard rounded rect 
    # with high radius is close enough for PIL
    
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=None, width=0)
    
    if outline and width > 0:
        draw.rounded_rectangle(xy, radius=radius, fill=None, outline=outline, width=width)

def draw_glass_panel(draw, xy, radius):
    """Draw a glass panel effect with highlight and shadow"""
    x1, y1, x2, y2 = xy
    
    # Main glass body
    draw_squircle(draw, xy, radius, fill=(255, 255, 255, 15))
    
    # Top/Left Highlight (Rim light)
    draw.line([(x1 + radius, y1), (x2 - radius, y1)], fill=(255, 255, 255, 100), width=1)
    draw.line([(x1, y1 + radius), (x1, y2 - radius)], fill=(255, 255, 255, 100), width=1)
    
    # Bottom/Right Shadow (Rim shadow)
    draw.line([(x1 + radius, y2), (x2 - radius, y2)], fill=(0, 0, 0, 40), width=1)
    draw.line([(x2, y1 + radius), (x2, y2 - radius)], fill=(0, 0, 0, 40), width=1)



def draw_text_with_glow_v2(image, text, position, font, color, glow_color, glow_radius=3):
    """
    Draw text with Gaussian blur glow.
    """
    draw = ImageDraw.Draw(image)
    x, y = position
    
    # Create a separate image for the glow
    # Make it large enough to hold the text + padding for blur
    # We need to measure text size first
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Padding for glow
    padding = glow_radius * 3
    
    # Create temp image
    glow_img = Image.new('RGBA', (text_width + padding * 2, text_height + padding * 2), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    
    # Draw text centered in temp image
    # Note: textbbox coordinates are relative to (0,0) but might have offset
    # We want to draw at (padding, padding) roughly, but need to account for font metrics
    # simpler: draw at (padding - bbox[0], padding - bbox[1]) to align top-left
    
    glow_draw.text((padding - bbox[0], padding - bbox[1]), text, font=font, fill=glow_color)
    
    # Apply blur
    glow_blurred = glow_img.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    
    # Paste glow onto main image
    # The position (x,y) is where the text starts.
    # We drew text at (padding - bbox[0], padding - bbox[1]) in glow_img.
    # So the top-left of glow_img corresponds to (x - (padding - bbox[0]), y - (padding - bbox[1]))?
    # Wait, 'position' usually means top-left of text or baseline depending on anchor.
    # Default anchor is 'la' (left, ascender).
    
    # Let's just use the same coordinates.
    # If we draw text at (x,y) on main image.
    # We want glow to be at same spot.
    
    # Paste location:
    paste_x = x - padding + bbox[0]
    paste_y = y - padding + bbox[1]
    
    # Actually, let's simplify. 
    # We paste the glow_blurred image such that the text inside it aligns with (x,y).
    # In glow_img, text is at (padding, padding) (roughly).
    # So we paste glow_img at (x - padding, y - padding).
    # But we need to be careful with bbox offsets.
    
    # Let's use a full-size layer for simplicity if performance allows, 
    # or just trust the padding math.
    
    # Draw text on glow_img at (padding, padding)
    glow_draw.text((padding, padding), text, font=font, fill=glow_color)
    glow_blurred = glow_img.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    
    # Paste
    image.paste(glow_blurred, (int(x - padding), int(y - padding)), glow_blurred)
    
    # Draw main text
    draw.text((x, y), text, fill=color, font=font)

async def generate_calendar_image_prototype(year: int, month: int, is_history: bool = False):
    # --- CONFIGURATION ---
    cell_size = 110
    header_height = 100
    day_header_height = 50
    padding = 50
    cols = 7
    rows = 6
    
    # Legend configuration (Right side)
    legend_width = 300
    
    # Calculate dimensions
    calendar_width = cols * cell_size + 2 * padding
    total_width = calendar_width + legend_width
    height = header_height + day_header_height + rows * cell_size + 2 * padding
    
    # Create background (Mesh Gradient)
    # Deep, rich colors for "Modern" look
    colors = [
        (10, 20, 40),    # Deep Blue
        (40, 10, 60),    # Deep Purple
        (0, 40, 60),     # Deep Teal
        (60, 20, 40),    # Deep Magenta
    ]
    bg_img = create_mesh_gradient(total_width, height, colors)
    
    # Add noise texture
    bg_img = add_noise(bg_img, intensity=20)
    
    # Create drawing context
    draw = ImageDraw.Draw(bg_img, "RGBA")
    
    # Fonts
    try:
        # Try to find a better font
        font_path_bold = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
        font_path_reg = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
        
        title_font = ImageFont.truetype(font_path_bold, 56)
        day_font = ImageFont.truetype(font_path_bold, 24)
        number_font = ImageFont.truetype(font_path_bold, 36)
        legend_font = ImageFont.truetype(font_path_reg, 24)
    except:
        title_font = ImageFont.load_default()
        day_font = ImageFont.load_default()
        number_font = ImageFont.load_default()
        legend_font = ImageFont.load_default()

    # --- MAIN GLASS PANEL ---
    # Draw a large glass panel container for the calendar
    panel_margin = 20
    draw_glass_panel(
        draw, 
        (panel_margin, panel_margin, calendar_width - panel_margin, height - panel_margin), 
        radius=30
    )

    # --- HEADER ---
    month_name_ukr = get_month_name_ukrainian(month)
    header_text = f"{month_name_ukr} {year}"
    bbox = draw.textbbox((0, 0), header_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (calendar_width - text_width) // 2
    text_y = padding + 10
    
    draw_text_with_glow_v2(bg_img, header_text, (text_x, text_y), title_font, (255, 255, 255, 255), (255, 255, 255, 150), glow_radius=8)

    # --- CALENDAR GRID ---
    y_start = header_height + padding
    
    # Day headers
    for i, day_abbr in enumerate(UKRAINIAN_DAYS):
        x = padding + i * cell_size
        y = y_start
        
        bbox = draw.textbbox((0, 0), day_abbr, font=day_font)
        tw = bbox[2] - bbox[0]
        tx = x + (cell_size - tw) // 2
        ty = y + (day_header_height - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), day_abbr, fill=(255, 255, 255, 180), font=day_font)

    # Days
    first_day = date(year, month, 1)
    first_weekday = first_day.weekday()
    y_start += day_header_height
    
    day_num = 1
    num_days = monthrange(year, month)[1]
    
    for row in range(rows):
        for col in range(cols):
            x = padding + col * cell_size
            y = y_start + row * cell_size
            
            # Cell box
            box = (x + 5, y + 5, x + cell_size - 5, y + cell_size - 5)
            
            if row == 0 and col < first_weekday:
                continue
            
            if day_num > num_days:
                break
                
            current_date = date(year, month, day_num)
            shift = MOCK_SHIFTS.get(current_date)
            
            # Day Cell Glass
            # More opaque for days with shifts
            if shift:
                fill_color = (255, 255, 255, 30)
                outline_color = (255, 255, 255, 80)
            else:
                fill_color = (255, 255, 255, 10)
                outline_color = (255, 255, 255, 30)
            
            draw_squircle(draw, box, radius=16, fill=fill_color, outline=outline_color, width=1)
            
            # Draw number
            draw.text((x + 15, y + 10), str(day_num), fill=(255, 255, 255, 220), font=number_font)
            
            # Draw user indicators (Modern: Colored bars at bottom of cell)
            if shift and shift.user_ids:
                bar_height = 6
                bar_y = y + cell_size - 20
                bar_width = (cell_size - 30) / len(shift.user_ids)
                start_x = x + 15
                
                for i, uid in enumerate(shift.user_ids):
                    user = next((u for u in MOCK_USERS if u.user_id == uid), None)
                    if user:
                        color = hex_to_rgb(user.color_code)
                        # Draw glowing bar
                        bx = start_x + i * bar_width
                        draw.rectangle(
                            [bx, bar_y, bx + bar_width - 2, bar_y + bar_height], 
                            fill=color + (255,)
                        )
                        # Add glow to bar
                        draw.rectangle(
                            [bx - 1, bar_y - 1, bx + bar_width - 1, bar_y + bar_height + 1], 
                            outline=color + (100,), width=1
                        )
            
            day_num += 1

    # --- LEGEND (RIGHT SIDE) ---
    legend_x = calendar_width
    legend_y = padding
    
    # Legend Glass Panel
    draw_glass_panel(
        draw, 
        (legend_x, legend_y, total_width - padding, height - padding), 
        radius=30
    )
    
    # Legend Title
    draw.text((legend_x + 30, legend_y + 30), "Легенда", fill=(255, 255, 255, 255), font=day_font)
    
    # Legend Items
    item_y = legend_y + 80
    for user in MOCK_USERS:
        color = hex_to_rgb(user.color_code)
        
        # Modern pill shape for user
        pill_box = (legend_x + 30, item_y, legend_x + 250, item_y + 40)
        draw_squircle(draw, pill_box, radius=20, fill=(255, 255, 255, 10))
        
        # Color indicator (Circle with glow)
        cx, cy = legend_x + 50, item_y + 20
        r = 8
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color + (255,))
        # Glow ring
        draw.ellipse([cx-r-2, cy-r-2, cx+r+2, cy+r+2], outline=color + (100,), width=2)
        
        # Name
        draw.text((legend_x + 80, item_y + 8), user.name, fill=(255, 255, 255, 220), font=legend_font)
        
        item_y += 55

    return bg_img

async def main():
    print("Generating advanced prototype calendar...")
    img = await generate_calendar_image_prototype(2025, 11)
    img.save("tests/calendar_test_v2.png")
    print("Saved to tests/calendar_test_v2.png")

if __name__ == "__main__":
    asyncio.run(main())
