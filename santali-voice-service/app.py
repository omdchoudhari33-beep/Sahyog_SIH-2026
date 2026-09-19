"""Self-hosted Santali ASR + translation + TTS, as a small internal HTTP
service - Bhashini has no Santali ("sat") model at all for any of these
three tasks (confirmed live against its own discovery endpoint - see
"1.Language normalizer/app/services/bhashini.py"), and the required
libraries (torch/transformers/parler-tts) fail to load natively on this
machine's Windows install (Smart App Control blocks their DLLs). Running
them inside this container - same pattern as Postgres/MinIO/Ollama in the
repo's docker-compose.yml - sidesteps that entirely; every OTHER SAHYOG
service still runs natively per the project's no-Docker-for-app-services
rule, this is purely an infra dependency like the database.

Models (loaded lazily, first request per task pays the cost):
- ASR:         facebook/mms-1b-all, "sat" adapter (Meta MMS). Open access.
- Translation: ai4bharat/indictrans2-{indic-en,en-indic}-dist-200M.
               Meta's NLLB-200-distilled-600M was tried first since it
               lists a "sat_Olck" code, but its tokenizer has no real
               Santali/Ol-Chiki vocabulary behind that code (confirmed
               live: it round-trips Ol Chiki characters as raw bytes, but
               the model was never actually trained on them - output was
               garbled, not a real translation). IndicTrans2 is AI4Bharat's
               own model family (same team as the ASR/TTS models here)
               and genuinely supports "sat_Olck" - gated on HuggingFace,
               needs HF_TOKEN (see docker-compose.yml).
- TTS:         ai4bharat/indic-parler-tts (Santali listed as supported).
               Also gated, needs the same HF_TOKEN.
"""
from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor

import soundfile as sf
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="santali-voice-service")

# All CUDA work is pinned to this single dedicated thread. FastAPI's sync
# endpoints below would otherwise each run in whichever thread its own
# threadpool happens to hand out (a different one per request) - live-
# tested and confirmed this produces silently WRONG results (garbled
# translation output, not an error) once a second model gets loaded and
# run from a different thread than the first, even though the exact same
# code in an isolated single-threaded script always gives correct output.
# Serializing every model call onto one persistent thread removes that
# variable entirely, at the cost of no cross-request parallelism (fine -
# this service already has a GPU-bound queue of one).
_gpu_executor = ThreadPoolExecutor(max_workers=1)


def _on_gpu_thread(fn, *args):
    return _gpu_executor.submit(fn, *args).result()

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info("santali-voice-service starting on device=%s", _DEVICE)

_ASR_MODEL_ID = "facebook/mms-1b-all"
_INDIC_EN_MODEL_ID = "ai4bharat/indictrans2-indic-en-dist-200M"
_EN_INDIC_MODEL_ID = "ai4bharat/indictrans2-en-indic-dist-200M"
_TTS_MODEL_ID = "ai4bharat/indic-parler-tts"

_asr_model = None
_asr_processor = None
_indic_en_model = None
_indic_en_tokenizer = None
_en_indic_model = None
_en_indic_tokenizer = None
_indic_processor = None
_tts_model = None
_tts_tokenizer = None
_tts_description_tokenizer = None


@app.get("/health")
def health():
    return {"status": "ok", "device": _DEVICE}


def _load_asr():
    global _asr_model, _asr_processor
    if _asr_model is None:
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        logger.info("loading %s (Santali ASR adapter) - first call only", _ASR_MODEL_ID)
        _asr_processor = AutoProcessor.from_pretrained(_ASR_MODEL_ID)
        _asr_processor.tokenizer.set_target_lang("sat")
        model = Wav2Vec2ForCTC.from_pretrained(_ASR_MODEL_ID)
        model.load_adapter("sat")
        _asr_model = model.to(_DEVICE).eval()
    return _asr_model, _asr_processor


def _do_asr(wav_bytes: bytes) -> dict:
    model, processor = _load_asr()
    audio, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    if sample_rate != 16000:
        raise HTTPException(400, f"expected 16kHz audio, got {sample_rate}Hz")

    inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
    inputs = {k: v.to(_DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits

    probs = torch.softmax(logits, dim=-1)
    confidence = probs.max(dim=-1).values.mean().item()
    ids = torch.argmax(logits, dim=-1)[0]
    transcript = processor.decode(ids)
    return {"transcript": transcript, "confidence": confidence}


@app.post("/asr")
async def asr(file: UploadFile = File(...)):
    """file must be 16kHz mono PCM WAV (the same normalize_audio() output
    every other language's ASR call already uses)."""
    try:
        wav_bytes = await file.read()
        return _on_gpu_thread(_do_asr, wav_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Santali ASR failed")
        raise HTTPException(500, f"Santali ASR failed: {exc}") from exc


def _load_indic_processor():
    global _indic_processor
    if _indic_processor is None:
        from IndicTransToolkit.processor import IndicProcessor

        _indic_processor = IndicProcessor(inference=True)
    return _indic_processor


def _load_indic_en():
    global _indic_en_model, _indic_en_tokenizer
    if _indic_en_model is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        logger.info("loading %s (Santali->English) - first call only", _INDIC_EN_MODEL_ID)
        _indic_en_tokenizer = AutoTokenizer.from_pretrained(_INDIC_EN_MODEL_ID, trust_remote_code=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(_INDIC_EN_MODEL_ID, trust_remote_code=True)
        _indic_en_model = model.to(_DEVICE).eval()
    return _indic_en_model, _indic_en_tokenizer


def _load_en_indic():
    global _en_indic_model, _en_indic_tokenizer
    if _en_indic_model is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        logger.info("loading %s (English->Santali) - first call only", _EN_INDIC_MODEL_ID)
        _en_indic_tokenizer = AutoTokenizer.from_pretrained(_EN_INDIC_MODEL_ID, trust_remote_code=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(_EN_INDIC_MODEL_ID, trust_remote_code=True)
        _en_indic_model = model.to(_DEVICE).eval()
    return _en_indic_model, _en_indic_tokenizer


_TRANSLATE_CODES = {"sat": "sat_Olck", "en": "eng_Latn"}


class TranslateRequest(BaseModel):
    text: str
    source: str  # "sat" or "en"
    target: str  # "sat" or "en"


def _do_translate(text: str, source: str, target: str, source_code: str, target_code: str) -> dict:
    model, tokenizer = _load_indic_en() if source == "sat" else _load_en_indic()
    ip = _load_indic_processor()

    batch = ip.preprocess_batch([text], src_lang=source_code, tgt_lang=target_code)
    inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True).to(_DEVICE)
    with torch.no_grad():
        generated = model.generate(**inputs, use_cache=True, min_length=0, max_length=256, num_beams=5)
    decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
    text_out = ip.postprocess_batch(decoded, lang=target_code)[0]
    return {"text": text_out}


@app.post("/translate")
def translate(payload: TranslateRequest):
    try:
        source_code = _TRANSLATE_CODES.get(payload.source)
        target_code = _TRANSLATE_CODES.get(payload.target)
        if not source_code or not target_code:
            raise HTTPException(400, f"unsupported language pair: {payload.source} -> {payload.target}")

        return _on_gpu_thread(_do_translate, payload.text, payload.source, payload.target, source_code, target_code)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Santali translation failed")
        raise HTTPException(500, f"Santali translation failed: {exc}") from exc


def _load_tts():
    global _tts_model, _tts_tokenizer, _tts_description_tokenizer
    if _tts_model is None:
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        logger.info("loading %s (Santali TTS) - first call only", _TTS_MODEL_ID)
        model = ParlerTTSForConditionalGeneration.from_pretrained(_TTS_MODEL_ID)
        _tts_model = model.to(_DEVICE).eval()
        _tts_tokenizer = AutoTokenizer.from_pretrained(_TTS_MODEL_ID)
        _tts_description_tokenizer = AutoTokenizer.from_pretrained(
            _tts_model.config.text_encoder._name_or_path
        )
    return _tts_model, _tts_tokenizer, _tts_description_tokenizer


class TtsRequest(BaseModel):
    text: str


def _do_tts(text: str) -> bytes:
    model, tokenizer, description_tokenizer = _load_tts()
    description = "A clear, natural speaker with high quality, calm audio."
    description_inputs = description_tokenizer(description, return_tensors="pt").to(_DEVICE)
    prompt_inputs = tokenizer(text, return_tensors="pt").to(_DEVICE)
    with torch.no_grad():
        generation = model.generate(
            input_ids=description_inputs.input_ids,
            attention_mask=description_inputs.attention_mask,
            prompt_input_ids=prompt_inputs.input_ids,
            prompt_attention_mask=prompt_inputs.attention_mask,
        )
    audio_arr = generation.to(torch.float32).cpu().numpy().squeeze()
    buf = io.BytesIO()
    sf.write(buf, audio_arr, model.config.sampling_rate, format="WAV")
    return buf.getvalue()


@app.post("/tts")
def tts(payload: TtsRequest):
    try:
        audio_bytes = _on_gpu_thread(_do_tts, payload.text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as exc:
        logger.exception("Santali TTS failed")
        raise HTTPException(500, f"Santali TTS failed: {exc}") from exc
