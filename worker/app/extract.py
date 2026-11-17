"""A blokk kiolvasása a helyi modellel. A nyers kimenet a bronzba kerül, a sémát a FIN-402 hozza."""

import base64
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO

import httpx
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

# 3: a kontextus 8192 token, a 2-es 4096 tokenje a fotónál elfogyott.
PROMPT_VERSION = "3"
# A szerkezetet a feldolgozó adja a szövegből, mert a modell JSON-módban rosszul párosított.
PROMPT = "Text Recognition:"
# A hosszabb oldal felső határa: 1000 px kb. 40, 1400 px kb. 80, 2000 px kb. 190 másodperc CPU-n.
# GPU-n a 2000 px 17 saját blokkon 1 `review` blokkot `ok`-ra javított, 24%-kal hosszabb modellidővel,
# ezért ott az OLLAMA_MAX_SIDE 2000.
MAX_SIDE = 1400
# Egy 30 tételes blokk kb. 750 token, 500-nál a JSON csonka maradt.
NUM_PREDICT = 2000
# A 2000 px-es kép legfeljebb kb. 4 100 képtoken (2000 × 2000-en mérve), a szöveg legfeljebb 2 000:
# a 8192 erre elég. A 4096-os alapkontextusban a fotó szövege a blokk közepén megszakadt.
NUM_CTX = 8192
# Csonka olvasásnál ugyanaz a kép nagyobb kontextussal és szöveghatárral megy újra, így sem nagyobb
# kép, sem nagyon hosszú blokk nem marad csendben csonka. A modell felső határa 131 072 token.
ATTEMPTS = ((NUM_CTX, NUM_PREDICT), (16384, 4000), (32768, 8000))
# A kontextus fogyott el: a szöveg csonka, más beállítással újra kell olvasni.
TRUNCATED = "length"


class ModelMissing(Exception):
    pass


def full_model_name(model: str) -> str:
    return model if ":" in model else f"{model}:latest"


def to_jpeg(image: Image.Image) -> bytes:
    output = BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=90)
    return output.getvalue()


def prepare_image(content: bytes, max_side: int = MAX_SIDE) -> bytes:
    """A modell bemenete: álló, kicsinyített JPEG. Az eredeti a Garage-ban változatlan marad."""
    with Image.open(BytesIO(content)) as image:
        upright = ImageOps.exif_transpose(image).convert("RGB")
    upright.thumbnail((max_side, max_side))
    return to_jpeg(upright)


# Az állapot képernyő átlaga ennyi olvasásra számol.
HISTORY_SIZE = 20


def seconds_of(result: dict, key: str) -> float:
    return round((result.get(key) or 0) / 1e9, 1)


def run_stats(result: dict) -> dict:
    """Az Ollama válaszának időadatai: betöltés, a kép feldolgozása, a szöveg generálása."""
    tokens = result.get("eval_count") or 0
    nanoseconds = result.get("eval_duration") or 0
    return {
        "finished_at": datetime.now(UTC).isoformat(),
        "seconds": seconds_of(result, "total_duration"),
        "load_seconds": seconds_of(result, "load_duration"),
        "image_seconds": seconds_of(result, "prompt_eval_duration"),
        "text_seconds": seconds_of(result, "eval_duration"),
        "tokens": tokens,
        "tokens_per_second": round(tokens / (nanoseconds / 1e9), 1) if nanoseconds else None,
    }


class ReceiptReader:
    def __init__(
        self,
        base_url: str,
        model: str,
        num_thread: int,
        keep_alive: str = "0",
        max_side: int = MAX_SIDE,
    ):
        self.name = model
        self.max_side = max_side
        self.num_thread = num_thread
        self.keep_alive = keep_alive
        # Az utolsó modellfutások ideje és sebessége az állapot képernyőnek.
        self.history: deque[dict] = deque(maxlen=HISTORY_SIZE)
        self.client = httpx.Client(base_url=base_url, timeout=httpx.Timeout(600, connect=5))

    @property
    def last_stats(self) -> dict | None:
        return self.history[-1] if self.history else None

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
            image = prepare_image(content, self.max_side)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            return {"error": f"A kép nem olvasható: {error}"}
        return self.read_image(image, report)

    def chat(self, image: bytes, num_ctx: int, num_predict: int, keep_alive: str) -> dict:
        response = self.client.post(
            "/api/chat",
            json={
                "model": self.name,
                "stream": False,
                "keep_alive": keep_alive,
                "options": {
                    "temperature": 0,
                    "num_thread": self.num_thread,
                    "num_predict": num_predict,
                    "num_ctx": num_ctx,
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
        return response.json()

    def read_image(self, image: bytes, report: Callable[[str], None]) -> dict:
        report("read_text")
        for attempt, (num_ctx, num_predict) in enumerate(ATTEMPTS, 1):
            # A nagyobb kontextusú modell az újrapróbálás után kirakódik, hogy ne foglalja a GPU-t.
            keep_alive = self.keep_alive if attempt == 1 else "0"
            result = self.chat(image, num_ctx, num_predict, keep_alive)
            if result.get("done_reason") != TRUNCATED:
                break
        stats = run_stats(result)
        self.history.append(stats)
        # Az időadatok a bronzba is bekerülnek, így újraindítás után is van mihez mérni.
        return {
            "ocr_text": result["message"]["content"],
            "done_reason": result.get("done_reason"),
            "seconds": stats["seconds"],
            "load_seconds": stats["load_seconds"],
            "image_seconds": stats["image_seconds"],
            "text_seconds": stats["text_seconds"],
            "tokens": stats["tokens"],
            "tokens_per_second": stats["tokens_per_second"],
            "max_side": self.max_side,
            # A képtoken és a kontextus mutatja, mennyire közel van az olvasás a határhoz.
            "prompt_tokens": result.get("prompt_eval_count"),
            "num_ctx": num_ctx,
            "attempts": attempt,
        }
