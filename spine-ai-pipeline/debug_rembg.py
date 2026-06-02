from rembg import remove
from PIL import Image
import sys

input_path = "input/archer_test.png"
output_path = "output/archer_test_rembg_debug.png"

print(f"Loading {input_path}")
img = Image.open(input_path)
print("Removing background...")
out = remove(img)
print(f"Saving to {output_path}")
out.save(output_path)
print("Done.")
