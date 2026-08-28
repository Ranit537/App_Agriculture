"""
AgriEdge - Local Flask server (phone -> laptop bridge).

Run:
    python app/app.py
Then open http://<laptop-ip>:5000 from a phone on the same Wi-Fi network.

Design note: the phone uploads via a normal form POST to /upload, which
redirects back to "/". Both the phone (right after its own upload) and
the laptop (which may have "/" open already, watching) pick up the
result the same way: a small JS poll against /api/latest every few
seconds. That's what makes "laptop displays the captured image" work
without needing websockets -- deliberately simple for a hackathon demo.
"""
import sys
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
UPLOAD_DIR = APP_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT / "ai" / "inference"))
import config  # noqa: E402
import sensor  # noqa: E402
from predict import predict_image, ModelNotFoundError, InferenceError  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# In-memory "latest result" -- intentionally simple for a hackathon demo:
# one active capture at a time, no database. Good enough for a live demo;
# not meant to survive a server restart or handle concurrent demos.
latest_result = {"has_result": False}

# Same pattern for the ESP32's readings -- one "latest" value, refreshed
# every time a new POST comes in from the sensor node.
latest_sensor = {"has_reading": False}


def set_latest_result(**fields):
    latest_result.clear()
    latest_result.update(has_result=True, timestamp=time.time(), **fields)


def set_latest_sensor(**fields):
    latest_sensor.clear()
    latest_sensor.update(has_reading=True, timestamp=time.time(), **fields)


@app.route("/")
def index():
    return render_template("index.html", crop=config.CROP_NAME)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("image")
    if file is None or file.filename == "":
        return render_template("index.html", crop=config.CROP_NAME, error="No image selected."), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return render_template(
            "index.html", crop=config.CROP_NAME, error=f"Unsupported file type '{ext}'."
        ), 400

    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / filename
    file.save(save_path)
    image_url = url_for("static", filename=f"uploads/{filename}")

    try:
        result = predict_image(str(save_path))
    except (ModelNotFoundError, InferenceError) as exc:
        set_latest_result(
            image_url=image_url, crop=config.CROP_NAME, prediction=None,
            confidence=None, status=config.STATUS_ERROR, recommendation=None,
            error=str(exc),
        )
        return redirect(url_for("index"))

    set_latest_result(image_url=image_url, **result)
    return redirect(url_for("index"))


@app.route("/api/latest")
def api_latest():
    """Clean JSON for the dashboard poller AND for Person 3's integration."""
    return jsonify(latest_result)


@app.route("/api/sensor", methods=["POST"])
def receive_sensor():
    """The ESP32 POSTs here every ~10s with its raw readings.

    Expected JSON body:
        {"moisture_raw": 2731, "temperature_c": 27.4, "humidity_pct": 61.2}
    Any field can be omitted/null (e.g. a bad DHT22 read) and is just
    skipped downstream in sensor.classify_reading().
    """
    if request.headers.get("X-API-Key") != config.SENSOR_API_KEY:
        return jsonify({"error": "Invalid or missing API key"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Expected a JSON body"}), 400

    set_latest_sensor(
        moisture_raw=data.get("moisture_raw"),
        temperature_c=data.get("temperature_c"),
        humidity_pct=data.get("humidity_pct"),
    )
    return jsonify({"ok": True})


@app.route("/api/sensor/latest")
def sensor_latest():
    """Raw reading + derived status/advice, for the dashboard poller."""
    if not latest_sensor.get("has_reading"):
        return jsonify(latest_sensor)

    stale = sensor.is_stale(latest_sensor.get("timestamp"))
    status, advice = sensor.classify_reading(
        latest_sensor.get("moisture_raw"),
        latest_sensor.get("temperature_c"),
        latest_sensor.get("humidity_pct"),
    )
    return jsonify({
        **latest_sensor,
        "status": config.SENSOR_STATUS_STALE if stale else status,
        "advice": advice,
    })


@app.route("/api/dashboard")
def dashboard_combined():
    """One combined feed: leaf result + sensor reading + merged advice.

    This is the endpoint Person 3's overall dashboard should hit if it
    wants a single call instead of polling /api/latest and
    /api/sensor/latest separately.
    """
    combined_advice = sensor.combine_with_leaf_result(latest_sensor, latest_result)
    return jsonify({
        "leaf": latest_result,
        "sensor": latest_sensor,
        "combined_advice": combined_advice,
    })


@app.errorhandler(413)
def too_large(_exc):
    return jsonify({"status": config.STATUS_ERROR, "error": "Image too large (max 10MB)."}), 413


if __name__ == "__main__":
    # debug=True is convenient for a hackathon demo (auto-reload, clear
    # error pages). Turn it off if this is ever exposed beyond a trusted
    # local Wi-Fi network.
    app.run(host="0.0.0.0", port=5000, debug=True)
