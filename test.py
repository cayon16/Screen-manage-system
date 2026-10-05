from PIL import Image
from pathlib import Path

input_path = Path(r"C:\Users\ADMIN\Pictures\anh_the_compressed.png")
output_path = input_path.with_name("final_anh_the.png")

with Image.open(input_path) as img:
    print(f"Kích thước gốc: {img.size}")

    # Giảm đúng 2 lần theo cả chiều rộng và chiều cao
    new_width = img.width // 2
    new_height = img.height // 2

    resized = img.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )

    # PNG lossless
    resized.save(
        output_path,
        format="PNG",
        optimize=True,
        compress_level=9
    )

    print(f"Kích thước mới: {resized.size}")

original_size = input_path.stat().st_size
new_size = output_path.stat().st_size

print(f"Dung lượng gốc : {original_size / 1024 / 1024:.2f} MB")
print(f"Dung lượng mới  : {new_size / 1024 / 1024:.2f} MB")
print(f"File output     : {output_path}")