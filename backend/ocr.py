"""Offline Thai OCR. Original PDF and page numbers are retained."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def available():
    return ((ROOT / 'vendor' / 'tesserocr').exists()
            and (ROOT / 'ocr_models' / 'tha.traineddata').exists()
            and shutil.which('pdftoppm') is not None)


def ocr_page(pdf: str, number: int) -> dict:
    if not available():
        raise RuntimeError('Thai OCR dependencies unavailable')
    vendor = str(ROOT / 'vendor')
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    import tesserocr
    work = ROOT / 'data' / 'ocr_work'
    work.mkdir(parents=True, exist_ok=True)
    # Temporary files stay inside the workspace; no cloud OCR transmission.
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        prefix = str(Path(tmp) / 'page')
        subprocess.run([shutil.which('pdftoppm'), '-f', str(number), '-l', str(number),
                        '-r', '220', '-singlefile', '-png', str(Path(pdf).resolve()), prefix],
                       check=True, capture_output=True, timeout=90)
        with tesserocr.PyTessBaseAPI(path=str(ROOT / 'ocr_models'), lang='tha+eng') as engine:
            engine.SetImageFile(prefix + '.png')
            text = engine.GetUTF8Text().strip()
            confidence = engine.MeanTextConf()
    return {'text': text, 'page_number': number, 'method': 'tesseract-tha-eng',
            'ocr_confidence': confidence, 'needs_text_review': True}


def cached_ocr(pdf: str, number: int) -> dict:
    cache = ROOT / 'data' / 'ocr_cache'
    cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
    path = cache / f'{digest}-p{number}-220dpi-v1.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    result = ocr_page(pdf, number)
    path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result
