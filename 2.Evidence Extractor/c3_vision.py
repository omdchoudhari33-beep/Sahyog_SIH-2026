import json
import base64
import requests
from schemas import VisualEvidence, ProcessingEngine

def audit_vision_evidence(image_path: str, complaint_text: str) -> VisualEvidence:
    """Analyzes visual evidence locally via Ollama's LLaVA model."""
    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        return VisualEvidence(
            image_analyzed=False,
            detailed_visual_analysis="System Error: Could not read image file.",
            discrepancy_notes=str(e),
            confidence=0.0
        )

    url = "http://localhost:11434/api/generate"
    
    prompt = f"""
    Analyze this image against the following citizen complaint: "{complaint_text}"
    
    Rules:
    1. detected_visual_elements: List of things seen in the photo.
    2. damage_type: Name the damage (e.g., pothole), or null.
    3. image_matches_report: true if photo matches the text, false otherwise.
    4. discrepancy_notes: Explain if there is a mismatch.
    5. confidence: float between 0.0 and 1.0.
    6. image_analyzed: true.
    7. detailed_visual_analysis: 2-3 sentences describing the scene.
    8. correlation_reasoning: Why it matches or doesn't match the complaint.
    
    Return ONLY JSON:
    {{
      "detected_visual_elements": ["..."],
      "damage_type": "...",
      "image_matches_report": true,
      "discrepancy_notes": "...",
      "confidence": 0.0,
      "image_analyzed": true,
      "detailed_visual_analysis": "...",
      "correlation_reasoning": "..."
    }}
    """
    
    payload = {
        "model": "llava",
        "prompt": prompt,
        "images": [encoded_image],
        "stream": False,
        "format": "json",
        # Keep the model resident between requests - reloading a 4.7GB
        # vision model from disk after each idle gap dwarfs actual
        # inference time. Also bound generation length: the JSON response
        # is always short, so an unbounded num_predict just risks the
        # model rambling and paying for tokens nobody reads.
        "keep_alive": "30m",
        "options": {"num_predict": 400, "temperature": 0.1},
    }

    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()
        
        # Defensively strip markdown
        if result_text.startswith("```json"): result_text = result_text[7:]
        if result_text.startswith("```"): result_text = result_text[3:]
        if result_text.endswith("```"): result_text = result_text[:-3]
            
        data = json.loads(result_text.strip())
        
        return VisualEvidence(
            detected_visual_elements=data.get("detected_visual_elements", []),
            damage_type=data.get("damage_type"),
            image_matches_report=bool(data.get("image_matches_report", False)),
            discrepancy_notes=data.get("discrepancy_notes"),
            confidence=float(data.get("confidence", 0.0)),
            engine_used=ProcessingEngine.LOCAL_OLLAMA,
            image_analyzed=bool(data.get("image_analyzed", True)),
            detailed_visual_analysis=data.get("detailed_visual_analysis", ""),
            correlation_reasoning=data.get("correlation_reasoning", "")
        )
        
    except Exception as e:
        print(f"C3 Vision Failure: {e}")
        return VisualEvidence(
            image_analyzed=False,
            detailed_visual_analysis="AI Processing Failed.",
            discrepancy_notes=str(e),
            confidence=0.0,
            engine_used=ProcessingEngine.LOCAL_OLLAMA
        )