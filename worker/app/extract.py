"""A blokk kiolvasása a helyi modellel. A nyers kimenet a bronzba kerül, a sémát a FIN-402 hozza."""

import base64
import json
from io import BytesIO

import httpx
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

PROMPT_VERSION = "1"
PROMPT = (
    "Extract the receipt into this JSON format, keep Hungarian accents, "
    "write prices as digits only:\n"
    '{"store":"","date":"","items":[{"name":"","price":""}],"total":"","payment_method":""}'
)
# Ollama structured output: a kényszer nélkül a modell néha vessző nélkül sorolta a tételeket.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "store": {"type": "string"},
        "date": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "price": {"type": "string"}},
                "required": ["name", "price"],
            },
        },
        "total": {"type": "string"},
        "payment_method": {"type": "string"},
    },
    "required": ["store", "date", "items", "total", "payment_method"],
}
# A szöveges mód a fotószerű mintákon is pontosabb volt, a JSON-é a szerkezet.
TEXT_PROMPT = "Text Recognition:"
# A hosszabb oldal felső határa: 1000 px kb. 40, 1400 px kb. 80, 2000 px kb. 190 másodperc CPU-n,
# és a mintákon 1400 fölött nem javult a pontosság.
MAX_SIDE = 1400
# Egy 30 tételes blokk kb. 750 token, 500-nál a JSON csonka maradt.
NUM_PREDICT = 2000


class ModelMissing(Exception):
    pass


def prepare_image(content: bytes) -> bytes:
    """A modell bemenete: álló, kicsinyített JPEG. Az eredeti a Garage-ban változatlan marad."""
    with Image.open(BytesIO(content)) as image:
        upright = ImageOps.exif_transpose(image).convert("RGB")
    upright.thumbnail((MAX_SIDE, MAX_SIDE))
    output = BytesIO()
    upright.save(output, format="JPEG", quality=90)
    return output.getvalue()


def parse_output(text: str) -> dict | None:
    """A kimenet ```json jelölésben is jöhet; a csonka vagy nem objektum kimenetből None lesz."""
    start, end = text.find("{"), text.rfind("}")
    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


class ReceiptReader:
    def __init__(self, base_url: str, model: str, num_thread: int):
        self.name = model
        self.num_thread = num_thread
        self.client = httpx.Client(base_url=base_url, timeout=httpx.Timeout(600, connect=5))

    def version(self) -> str:
        """A modell azonosítója, így minden kiolvasásról tudni, melyik modellváltozat adta."""
        response = self.client.get("/api/tags")
        response.raise_for_status()
        wanted = self.name if ":" in self.name else f"{self.name}:latest"
        for model in response.json()["models"]:
            if model["name"] == wanted:
                return model["digest"]
        raise ModelMissing(f"A {wanted} modell hiányzik, futtasd a scripts/ollama-pull.sh-t.")

    def chat(self, prompt: str, image: bytes, output_format: dict | None = None) -> dict:
        request = {
            "model": self.name,
            "stream": False,
            "keep_alive": "0",
            "options": {
                "temperature": 0,
                "num_thread": self.num_thread,
                "num_predict": NUM_PREDICT,
            },
            "messages": [
                {"role": "user", "content": prompt, "images": [base64.b64encode(image).decode()]}
            ],
        }
        if output_format:
            request["format"] = output_format
        response = self.client.post("/api/chat", json=request)
        response.raise_for_status()
        return response.json()

    def read(self, content: bytes) -> dict:
        """A bronzba kerülő eredmény. A kapcsolati hiba kivétel, így a tétel nyitva marad."""
        try:
            image = prepare_image(content)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            return {"error": f"A kép nem olvasható: {error}"}
        structured = self.chat(PROMPT, image, OUTPUT_SCHEMA)
        text = self.chat(TEXT_PROMPT, image)
        nanoseconds = structured.get("total_duration", 0) + text.get("total_duration", 0)
        return {
            "raw_text": structured["message"]["content"],
            "parsed": parse_output(structured["message"]["content"]),
            "ocr_text": text["message"]["content"],
            "done_reason": structured.get("done_reason"),
            "seconds": round(nanoseconds / 1e9, 1),
        }
