#!/usr/bin/env python3
"""
Download a sample face image from an open-source dataset for testing
This uses publicly available face images for testing purposes only
"""

import urllib.request
import os
from pathlib import Path

def download_sample_face(filename="sample_face.jpg"):
    """
    Download a sample face image from a public dataset.
    Using LFW (Labeled Faces in the Wild) dataset which is free for research.
    """
    
    # Sample face from LFW dataset (public domain, free to use for testing)
    # This is a small sample image that will work great for testing
    url = "https://vis-www.cs.umass.edu/lfw/lfw-deepfunneled/Aaron_Eckhart/Aaron_Eckhart_0001.jpg"
    
    try:
        print("Downloading sample face image from LFW dataset...")
        print(f"Source: {url}")
        
        urllib.request.urlretrieve(url, filename)
        
        file_size = os.path.getsize(filename)
        print(f"✓ Downloaded successfully: {filename} ({file_size:,} bytes)")
        print(f"\nTo use this for testing:")
        print(f"1. Go to http://localhost:5000")
        print(f"2. Click 'Enroll Face' → 'Upload Image'")
        print(f"3. Enter a name: 'Aaron Eckhart'")
        print(f"4. Upload: {os.path.abspath(filename)}")
        print(f"5. Click 'Enroll from Image'")
        print(f"\nFace enrollment should now work!")
        
        return filename
        
    except Exception as e:
        print(f"✗ Failed to download: {e}")
        print("\nAlternative: Use a real face photo from your computer")
        print("Make sure the image has:")
        print("  - One clear face (front-facing preferred)")
        print("  - Good lighting")
        print("  - JPG or PNG format")
        return None

if __name__ == '__main__':
    import sys
    filename = sys.argv[1] if len(sys.argv) > 1 else "sample_face.jpg"
    download_sample_face(filename)
