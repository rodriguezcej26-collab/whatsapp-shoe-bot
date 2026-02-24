import os
import base64
import json
import logging
import gspread
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Inventario Calzado")
WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "inventario")


def get_gemini_client():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    return genai.GenerativeModel("gemini-1.5-flash")


def get_sheet_client():
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google_service_account.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client


def get_all_products() -> list[dict]:
    try:
        client = get_sheet_client()
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
        records = sheet.get_all_records()
        logger.info(f"Inventario cargado: {len(records)} productos")
        return records
    except Exception as e:
        logger.error(f"Error leyendo Google Sheets: {e}")
        return []


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def extract_json(text: str) -> dict:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)


async def search_by_text(query: str) -> list[dict]:
    products = get_all_products()
    if not products:
        return []

    catalog = "\n".join([
        f"- Ref:{p.get('referencia')} | Nombre:{p.get('nombre')} | Color:{p.get('color')} | "
        f"Tallas:{p.get('tallas_disponibles')} | Cantidad:{p.get('cantidad')}"
        for p in products
    ])

    prompt = f"""Eres el asistente de una tienda de calzado. El cliente busca: "{query}"

Inventario disponible:
{catalog}

Identifica cuál producto coincide mejor. Considera nombre, color y talla.

Responde SOLO con JSON sin texto adicional:
{{"referencia": "REF_AQUI", "coincidencia": true}}

Si no hay coincidencia: {{"coincidencia": false}}"""

    try:
        model = get_gemini_client()
        response = model.generate_content(prompt)
        result = extract_json(response.text)

        if result.get("coincidencia") and result.get("referencia"):
            ref = result["referencia"]
            matched = [p for p in products if str(p.get("referencia")) == str(ref)]
            return matched if matched else []
        return []

    except Exception as e:
        logger.error(f"Error en búsqueda por texto: {e}")
        query_lower = query.lower()
        matches = []
        for p in products:
            name_sim = similarity(query_lower, str(p.get("nombre", "")))
            color_mentioned = str(p.get("color", "")).lower() in query_lower
            if name_sim > 0.4 or color_mentioned:
                matches.append((p, name_sim))
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:3]]


async def search_by_image(image_bytes: bytes) -> list[dict]:
    products = get_all_products()
    if not products:
        return []

    catalog = "\n".join([
        f"- Ref:{p.get('referencia')} | Nombre:{p.get('nombre')} | Color:{p.get('color')} | "
        f"Tallas:{p.get('tallas_disponibles')} | Cantidad:{p.get('cantidad')}"
        for p in products
    ])

    prompt = f"""Eres el asistente de una tienda de calzado.
El cliente envió esta foto de un zapato que busca.

Analiza la imagen e identifica tipo, color y marca si es visible.
Compara con este inventario y encuentra el más similar:
{catalog}

Responde SOLO con JSON sin texto adicional:
{{"referencia": "REF_DEL_PRODUCTO", "coincidencia": true, "descripcion_imagen": "descripción breve"}}

Si no hay coincidencia: {{"coincidencia": false, "descripcion_imagen": "descripción breve"}}"""

    try:
        import PIL.Image
        import io

        model = get_gemini_client()
        image = PIL.Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([prompt, image])
        result = extract_json(response.text)
        logger.info(f"Análisis de imagen: {result}")

        if result.get("coincidencia") and result.get("referencia"):
            ref = result["referencia"]
            matched = [p for p in products if str(p.get("referencia")) == str(ref)]
            return matched if matched else []
        return []

    except Exception as e:
        logger.error(f"Error en búsqueda por imagen: {e}")
        return []


async def find_similar_products(product: dict) -> list[dict]:
    all_products = get_all_products()
    target_name = str(product.get("nombre", "")).lower()
    target_color = str(product.get("color", "")).lower()
    target_ref = str(product.get("referencia", ""))

    similar = []
    for p in all_products:
        if str(p.get("referencia")) == target_ref:
            continue
        if int(p.get("cantidad", 0)) <= 0:
            continue
        name_sim = similarity(target_name, str(p.get("nombre", "")))
        color_sim = similarity(target_color, str(p.get("color", "")))
        score = (name_sim * 0.7) + (color_sim * 0.3)
        if score > 0.35:
            similar.append((p, score))

    similar.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in similar[:3]]
