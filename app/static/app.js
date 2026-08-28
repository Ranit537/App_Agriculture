const POLL_INTERVAL_MS = 4000;

const el = {
  empty: document.getElementById("result-empty"),
  content: document.getElementById("result-content"),
  image: document.getElementById("result-image"),
  badge: document.getElementById("status-badge"),
  meterFill: document.getElementById("meter-fill"),
  crop: document.getElementById("result-crop"),
  prediction: document.getElementById("result-prediction"),
  confidence: document.getElementById("result-confidence"),
  recommendation: document.getElementById("result-recommendation"),
};

const STATUS_STYLES = {
  HEALTHY: { label: "Healthy", cls: "healthy" },
  DISEASE_DETECTED: { label: "Disease Detected", cls: "disease" },
  UNCERTAIN: { label: "Uncertain", cls: "uncertain" },
  ERROR: { label: "Error", cls: "error" },
};

function render(data) {
  if (!data.has_result) {
    el.empty.classList.remove("hidden");
    el.content.classList.add("hidden");
    return;
  }

  el.empty.classList.add("hidden");
  el.content.classList.remove("hidden");

  el.image.src = data.image_url || "";

  const style = STATUS_STYLES[data.status] || STATUS_STYLES.ERROR;
  el.badge.textContent = style.label;
  el.badge.className = `badge badge-${style.cls}`;
  el.meterFill.className = `meter-fill fill-${style.cls}`;

  const confidencePct = data.confidence != null ? data.confidence * 100 : 0;
  el.meterFill.style.width = `${confidencePct}%`;

  el.crop.textContent = data.crop || "--";

  if (data.status === "ERROR") {
    el.prediction.textContent = "--";
    el.confidence.textContent = "--";
    el.recommendation.textContent = data.error || "Something went wrong.";
  } else {
    el.prediction.textContent = data.prediction || "--";
    el.confidence.textContent = data.confidence != null ? `${confidencePct.toFixed(1)}%` : "--";
    el.recommendation.textContent = data.recommendation || "--";
  }
}

const sensorEl = {
  empty: document.getElementById("sensor-empty"),
  content: document.getElementById("sensor-content"),
  badge: document.getElementById("sensor-badge"),
  moisture: document.getElementById("sensor-moisture"),
  temp: document.getElementById("sensor-temp"),
  humidity: document.getElementById("sensor-humidity"),
  advice: document.getElementById("sensor-advice"),
};

const SENSOR_STYLES = {
  OK: { label: "OK", cls: "healthy" },
  WARNING: { label: "Warning", cls: "uncertain" },
  STALE: { label: "Offline", cls: "error" },
};

function renderSensor(data) {
  if (!data.has_reading) {
    sensorEl.empty.classList.remove("hidden");
    sensorEl.content.classList.add("hidden");
    return;
  }

  sensorEl.empty.classList.add("hidden");
  sensorEl.content.classList.remove("hidden");

  const style = SENSOR_STYLES[data.status] || SENSOR_STYLES.WARNING;
  sensorEl.badge.textContent = style.label;
  sensorEl.badge.className = `badge badge-${style.cls}`;

  sensorEl.moisture.textContent =
    data.moisture_raw != null ? `${data.moisture_raw} (raw)` : "--";
  sensorEl.temp.textContent =
    data.temperature_c != null ? `${data.temperature_c.toFixed(1)} \u00b0C` : "--";
  sensorEl.humidity.textContent =
    data.humidity_pct != null ? `${data.humidity_pct.toFixed(1)} %` : "--";
  sensorEl.advice.textContent =
    data.advice && data.advice.length ? data.advice.join(" ") : "Conditions look normal.";
}

async function refresh() {
  try {
    const res = await fetch("/api/latest");
    if (res.ok) render(await res.json());
  } catch (err) {
    console.error("Could not refresh latest result:", err);
  }

  try {
    const res = await fetch("/api/sensor/latest");
    if (res.ok) renderSensor(await res.json());
  } catch (err) {
    console.error("Could not refresh sensor reading:", err);
  }
}

refresh();
setInterval(refresh, POLL_INTERVAL_MS);
