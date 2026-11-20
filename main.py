import hashlib
import io
import os
import requests
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Веб-приложение обработки изображений")

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

RECAPTCHA_SITE_KEY = "6Le8PiouAAAAAPAZkaXLkQF0eytGn-XCCNu6tCRD"
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "YOUR_SECRET_KEY")

def resize_image(image: Image.Image, scale_factor: float) -> Image.Image:
    if scale_factor <= 0:
        raise ValueError("Коэффициент масштабирования должен быть больше 0")
    width, height = image.size
    new_width = max(1, int(width * scale_factor))
    new_height = max(1, int(height * scale_factor))
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def save_color_histogram(image: Image.Image, save_path: str, title_prefix: str):
    img_array = np.array(image.convert("RGB"))
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))

    colors = [('red', 'Red (R)', 0), ('green', 'Green (G)', 1), ('blue', 'Blue (B)', 2)]
    for color, label, channel_idx in colors:
        hist, _ = np.histogram(img_array[:, :, channel_idx], bins=256, range=(0, 256))
        axes[channel_idx].plot(hist, color=color, linewidth=1.2)
        axes[channel_idx].set_title(f"{title_prefix}: {label}")
        axes[channel_idx].set_xlabel("Значение цвета (0-255)")
        axes[channel_idx].set_ylabel("Частота")
        axes[channel_idx].grid(True, linestyle='--', alpha=0.4)

    plt.tight_layout()
    fig.savefig(save_path, format='png', dpi=120)
    plt.close(fig)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "ready": False,
            "site_key": RECAPTCHA_SITE_KEY
        }
    )


@app.post("/process", response_class=HTMLResponse)
async def process_image(
    request: Request,
    scale_factor: float = Form(...),
    file: UploadFile = File(...),
    resp: str = Form(default="")
):
    if RECAPTCHA_SECRET_KEY and RECAPTCHA_SECRET_KEY != "YOUR_SECRET_KEY":
        try:
            payload = {"secret": RECAPTCHA_SECRET_KEY, "response": resp}
            verify_response = requests.post(
                "https://google.com/recaptcha/api/siteverify",
                data=payload,
                timeout=5
            )
            if verify_response.status_code == 200 and verify_response.text:
                if not verify_response.json().get("success"):
                    raise HTTPException(status_code=400, detail="Ошибка проверки капчи")
        except requests.RequestException:
            raise HTTPException(status_code=503, detail="Не удалось связаться с сервером reCAPTCHA")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    if scale_factor < 0.1 or scale_factor > 5.0:
        raise HTTPException(status_code=400, detail="Масштаб должен быть в диапазоне от 0.1 до 5.0")

    contents = await file.read()
    orig_img = Image.open(io.BytesIO(contents)).convert("RGB")
    orig_size = orig_img.size

    resized_img = resize_image(orig_img, scale_factor)
    resized_size = resized_img.size

    file_hash = hashlib.sha256(f"{file.filename}_{scale_factor}".encode("utf-8")).hexdigest()[:12]

    orig_filename = f"{file_hash}_orig.png"
    resized_filename = f"{file_hash}_resized.png"
    hist_orig_filename = f"{file_hash}_hist_orig.png"
    hist_resized_filename = f"{file_hash}_hist_resized.png"

    orig_img.save(f"./static/{orig_filename}", "PNG")
    resized_img.save(f"./static/{resized_filename}", "PNG")

    save_color_histogram(orig_img, f"./static/{hist_orig_filename}", "Исходное")
    save_color_histogram(resized_img, f"./static/{hist_resized_filename}", "Измененное")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "ready": True,
            "site_key": RECAPTCHA_SITE_KEY,
            "scale_factor": scale_factor,
            "orig_size": f"{orig_size[0]}x{orig_size[1]}",
            "resized_size": f"{resized_size[0]}x{resized_size[1]}",
            "orig_url": f"/static/{orig_filename}",
            "resized_url": f"/static/{resized_filename}",
            "hist_orig_url": f"/static/{hist_orig_filename}",
            "hist_resized_url": f"/static/{hist_resized_filename}",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
