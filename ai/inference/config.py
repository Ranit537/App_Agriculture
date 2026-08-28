"""
AgriEdge - Centralized configuration (Person 1 - Edge AI).

Every other file reads class names, paths, and thresholds from here.
Nothing disease-specific lives in predict.py or app.py: adding a future
disease means adding data here (and retraining) -- never a new
`if prediction == "..."` branch anywhere in the codebase.
"""

import json
from pathlib import Path

# --- Paths ----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "ai" / "models"

# "Current" model: whatever is deployed right now. When you train a new
# version, back the old file up with a version suffix (e.g.
# tomato_disease_model_v1.tflite) and save the new export over this
# filename, so the app never needs a source change to pick it up.
MODEL_PATH = MODEL_DIR / "tomato_disease_model.tflite"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

# --- Defaults (used until model_metadata.json exists, i.e. before you've
# trained anything -- and kept in sync afterwards, see bottom of file) ----
CROP_NAME = "Tomato"
MODEL_VERSION = "v1"
IMAGE_SIZE = (224, 224)  # (height, width) - MUST match training
CLASS_NAMES = ["Healthy", "Early Blight", "Late Blight"]
HEALTHY_LABEL = "Healthy"

# --- Confidence -------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.80  # below this we report "Uncertain" rather than guess

# --- Status codes (shared by predict.py, app.py, and Person 2/3) -----------
STATUS_HEALTHY = "HEALTHY"
STATUS_DISEASE_DETECTED = "DISEASE_DETECTED"
STATUS_UNCERTAIN = "UNCERTAIN"
STATUS_ERROR = "ERROR"

# --- Farmer-facing recommendations, keyed by class name ---------------------
# Adding a disease later = add a key here + retrain. No code changes.
RECOMMENDATIONS = {
    "Healthy": "No signs of disease detected. Continue regular monitoring.",
    "Early Blight": (
        "Possible early blight. Remove and dispose of affected lower leaves, "
        "avoid overhead watering, and improve airflow around the plant."
    ),
    "Late Blight": (
        "Possible late blight. This spreads quickly in humid conditions -- "
        "remove affected leaves promptly and consult a local agricultural "
        "extension officer."
    ),
    "Uncertain": (
        "The model isn't confident enough to classify this image. Try a "
        "clearer, well-lit photo of a single leaf against a plain background."
    ),
}
DEFAULT_RECOMMENDATION = "No recommendation configured for this class yet."

# --- Sensor thresholds (Person 2 - Sensor Fusion / ESP32) -------------------
# Calibrate SOIL_DRY_RAW_THRESHOLD / SOIL_WET_RAW_THRESHOLD against your own
# probe: dip it in a dry pot and a freshly watered pot, print moistureRaw
# over Serial, and set these to what you actually see. Most cheap capacitive
# probes read HIGHER when dry and LOWER when wet -- if yours is the
# opposite, just swap the comparison in sensor.py's classify_reading().
SOIL_DRY_RAW_THRESHOLD = 3000   # raw ADC value at/above which soil is "dry"
SOIL_WET_RAW_THRESHOLD = 1500   # raw ADC value at/below which soil is "waterlogged"

TEMP_LOW_C = 10.0
TEMP_HIGH_C = 32.0

HUMIDITY_LOW_PCT = 30.0
HUMIDITY_HIGH_PCT = 85.0

SENSOR_STATUS_OK = "OK"
SENSOR_STATUS_WARNING = "WARNING"
SENSOR_STATUS_STALE = "STALE"       # no reading received recently -> ESP32 likely offline
SENSOR_STALE_AFTER_SECONDS = 30     # ESP32 posts every ~10s, so 3 missed = stale

SENSOR_ADVICE = {
    "dry_soil": "Soil is dry -- irrigate soon.",
    "wet_soil": "Soil is waterlogged -- hold off watering and check drainage.",
    "low_temp": "Temperature is low for tomatoes -- consider row covers.",
    "high_temp": "Temperature is high -- provide shade or increase watering frequency.",
    "low_humidity": "Humidity is low -- consider misting or mulching.",
    "high_humidity": "Humidity is high -- raises fungal disease risk (blight); improve airflow.",
}

# A simple shared secret so random devices on the same Wi-Fi can't spam
# your /api/sensor endpoint. Change this, and put the same value in the
# ESP32 sketch's API_KEY constant.
SENSOR_API_KEY = "agriedge-demo-key-change-me"

# --- Load real metadata from the trained model, if it exists ----------------
# Keeps class order/version in sync with whatever was actually trained,
# without hand-editing this file every time the model changes.
if METADATA_PATH.exists():
    try:
        with open(METADATA_PATH, "r") as f:
            _metadata = json.load(f)
        CLASS_NAMES = _metadata.get("class_names", CLASS_NAMES)
        MODEL_VERSION = _metadata.get("model_version", MODEL_VERSION)
        _size = _metadata.get("input_size")
        if _size:
            IMAGE_SIZE = tuple(_size)
    except (json.JSONDecodeError, OSError):
        pass  # fall back to defaults above; predict.py will surface load errors
