#!/usr/bin/env python3
"""
Test Face Image Generator - Create a sample face image for testing enrollment
without needing a working camera
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

def create_simple_face_image(name="TestFace", filename="test_face.jpg"):
    """
    Create a simple but realistic-looking face image for testing.
    Uses PIL to draw a basic face shape.
    """
    
    # Create a new RGB image with light background
    img = Image.new('RGB', (640, 480), color=(200, 180, 160))  # skin tone background
    draw = ImageDraw.Draw(img)
    
    # Head ellipse
    head_left, head_top = 220, 80
    head_right, head_bottom = 420, 320
    draw.ellipse([head_left, head_top, head_right, head_bottom], fill=(220, 200, 180), outline=(100, 80, 60), width=2)
    
    # Eyes
    eye_y = 160
    left_eye = (280, eye_y, 310, eye_y + 30)
    right_eye = (330, eye_y, 360, eye_y + 30)
    draw.ellipse(left_eye, fill=(255, 255, 255), outline=(0, 0, 0), width=1)
    draw.ellipse(right_eye, fill=(255, 255, 255), outline=(0, 0, 0), width=1)
    
    # Pupils
    draw.ellipse((290, 168, 300, 178), fill=(100, 50, 50))  # left pupil
    draw.ellipse((340, 168, 350, 178), fill=(100, 50, 50))  # right pupil
    
    # Eyebrows
    draw.arc([275, 145, 315, 165], 0, 180, fill=(100, 50, 20), width=2)
    draw.arc([325, 145, 365, 165], 0, 180, fill=(100, 50, 20), width=2)
    
    # Nose
    nose_x = 320
    draw.polygon([(nose_x, 160), (nose_x-8, 210), (nose_x+8, 210)], outline=(150, 120, 100), width=2)
    
    # Mouth
    mouth_y = 260
    draw.arc([280, mouth_y, 360, mouth_y + 40], 0, 180, fill=(200, 80, 80), width=3)
    
    # Hair
    draw.polygon([
        (220, 120), (200, 80), (320, 60), (420, 80), (400, 120)
    ], fill=(60, 30, 10), outline=(40, 10, 0), width=2)
    
    # Add name text
    try:
        draw.text((320, 400), f"Test: {name}", fill=(0, 0, 0), anchor="mm")
    except:
        pass  # font might not be available
    
    # Save image
    img.save(filename)
    print(f"✓ Created test face image: {filename}")
    print(f"  You can now upload this image to test enrollment")
    return filename

if __name__ == '__main__':
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "TestFace"
    filename = sys.argv[2] if len(sys.argv) > 2 else "test_face.jpg"
    
    create_simple_face_image(name, filename)
    
    # Also show how to use it
    print(f"\nUsage in Flask:")
    print(f"1. Visit http://localhost:5000")
    print(f"2. Go to 'Enroll Face' → 'Upload Image'")
    print(f"3. Enter name: {name}")
    print(f"4. Upload file: {os.path.abspath(filename)}")
    print(f"5. Click 'Enroll from Image'")
