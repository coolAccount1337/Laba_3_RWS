from PIL import Image
import main


def test_resize_image():
    img = Image.new("RGB", (100, 200), color="red")
    resized = main.resize_image(img, 0.5)
    assert resized.size == (50, 100)
