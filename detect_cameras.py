#!/usr/bin/env python3
"""
Camera Device Detector - Find available camera devices on Windows
Run this to see which cameras are available and working
"""

import cv2
import sys

def test_camera_device(device_index, timeout=3):
    """Test if a camera device is available and working."""
    try:
        print(f"\n[Testing Device {device_index}]")
        cap = cv2.VideoCapture(device_index)
        
        if not cap.isOpened():
            print(f"  ✗ Failed to open")
            return False
        
        # Try to read a frame
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"  ✓ Working! Resolution: {w}x{h}")
            return True
        else:
            print(f"  ✗ Opened but can't read frames")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("Windows Camera Device Detector")
    print("=" * 50)
    
    found_any = False
    for i in range(10):
        if test_camera_device(i):
            found_any = True
    
    if not found_any:
        print("\n" + "!" * 50)
        print("⚠  NO WORKING CAMERAS DETECTED")
        print("!" * 50)
        print("\nPossible solutions:")
        print("1. Check if another app is using your camera (Teams, Zoom, etc.)")
        print("2. Restart your computer")
        print("3. Update your camera drivers")
        print("4. Check if camera is enabled in Windows Settings")
        print("5. Try a different USB camera")
        print("6. Use image upload for enrollment instead")
        sys.exit(1)
    else:
        print("\n✓ Found at least one working camera!")
        print("You can now run: python windows_camera_server.py --camera 0")
