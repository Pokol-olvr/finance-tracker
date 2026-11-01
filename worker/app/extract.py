"""A blokk kiolvasása a helyi modellel. A nyers kimenet a bronzba kerül, a sémát a FIN-402 hozza."""

import base64
from collections.abc import Callable
from io import BytesIO

import httpx
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

PROMPT_VERSION = "2"
# A szerkezetet a feldolgozó adja a szövegből, mert a modell JSON-módban rosszul párosított.
PROMPT = "Text Recognition:"
# A hosszabb oldal felső határa: 1000 px kb. 40, 1400 px kb. 80, 2000 px kb. 190 másodperc CPU-n,
# és a mintákon 1400 fölött nem javult a pontosság.
MAX_SIDE = 1400
# Egy 30 tételes blokk kb. 750 token, 500-nál a JSON csonka maradt.
NUM_PREDICT = 2000


class ModelMissing(Exception):
    pass


def full_model_name(model: str) -> str:
    return model if ":" in model else f"{model}:latest"


def to_jpeg(image: Image.Image) -> bytes:
    output = BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=90)
    return output.getvalue()


def prepare_image(content: bytes) -> bytes:
    """A modell bemenete: álló, kicsinyített JPEG. Az eredeti a Garage-ban változatlan marad."""
    with Image.open(BytesIO(content)) as image:
        upright = ImageOps.exif_transpose(image).convert("RGB")
    upright.thumbnail((MAX_SIDE, MAX_SIDE))
    return to_jpeg(upright)


class ReceiptReader:
    def __init__(self, base_url: str, model: str, num_thread: int):
        self.name = model
        self.num_thread = num_thread
        self.client = httpx.Client(base_url=base_url, timeout=httpx.Timeout(600, connect=5))

    def version(self) -> str:
        """A modell azonosítója, így minden kiolvasásról tudni, melyik modellváltozat adta."""
        response = self.client.get("/api/tags")
        response.raise_for_status()
        wanted = full_model_name(self.name)
        for model in response.json()["models"]:
            if model["name"] == wanted:
                return model["digest"]
        raise ModelMissing(f"A {wanted} modell hiányzik, futtasd a scripts/ollama-pull.sh-t.")

    def read(self, content: bytes, report: Callable[[str], None]) -> dict:
        """A bronzba kerülő eredmény. A kapcsolati hiba kivétel, így a tétel nyitva marad."""
        try:
            image = prepare_image(content)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            return {"error": f"A kép nem olvasható: {error}"}
        return self.read_image(image, report)

    def read_image(self, image: bytes, report: Callable[[str], None]) -> dict:
        report("read_text")
        response = self.client.post(
            "/api/chat",
            json={
                "model": self.name,
                "stream": False,
                "keep_alive": "0",
                "options": {
                    "temperature": 0,
                    "num_thread": self.num_thread,
                    "num_predict": NUM_PREDICT,
                },
                "messages": [
                    {
                        "role": "user",
                        "content": PROMPT,
                        "images": [base64.b64encode(image).decode()],
                    }
                ],
            },
        )
        response.raise_for_status()
        result = response.json()
        return {
            "ocr_text": result["message"]["content"],
            "done_reason": result.get("done_reason"),
            "seconds": round(result.get("total_duration", 0) / 1e9, 1),
        }
