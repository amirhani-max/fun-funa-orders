"""
Generate a QR code for the Fun Fana ordering page.
Usage:
    python generate_qr.py
    python generate_qr.py http://your-public-url.com
"""

import sys
import qrcode
from pathlib import Path

def generate(url: str = "http://localhost:8000"):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#4F46E5", back_color="white")
    output = Path(__file__).parent / "fun_fana_qr.png"
    img.save(output)
    print(f"QR code saved to: {output}")
    print(f"Points to: {url}")
    print("Print this image and place it in your shop.")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    generate(url)
