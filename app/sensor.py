"""
AgriEdge - Sensor fusion / decision engine (Person 2 - Sensor Data).

Takes raw ESP32 readings (soil moisture ADC value, temperature, humidity)
and turns them into a status + plain-language advice, using the
thresholds in config.py. Also merges that with the latest leaf-disease
result from predict.py so the dashboard can show one unified picture
(this is the "decision engine" mentioned in README section 20).

Nothing here talks to the ESP32 directly -- app.py receives the HTTP
POST and just passes the numbers into classify_reading().
"""
import time

import config


def classify_reading(moisture_raw, temperature_c, humidity_pct):
    """Return (status, [advice strings]) for one sensor reading.

    Any of the three values can be None (e.g. a DHT22 misread) -- that
    signal is simply skipped rather than treated as an error.
    """
    advice = []

    if moisture_raw is not None:
        if moisture_raw >= config.SOIL_DRY_RAW_THRESHOLD:
            advice.append(config.SENSOR_ADVICE["dry_soil"])
        elif moisture_raw <= config.SOIL_WET_RAW_THRESHOLD:
            advice.append(config.SENSOR_ADVICE["wet_soil"])

    if temperature_c is not None:
        if temperature_c <= config.TEMP_LOW_C:
            advice.append(config.SENSOR_ADVICE["low_temp"])
        elif temperature_c >= config.TEMP_HIGH_C:
            advice.append(config.SENSOR_ADVICE["high_temp"])

    if humidity_pct is not None:
        if humidity_pct <= config.HUMIDITY_LOW_PCT:
            advice.append(config.SENSOR_ADVICE["low_humidity"])
        elif humidity_pct >= config.HUMIDITY_HIGH_PCT:
            advice.append(config.SENSOR_ADVICE["high_humidity"])

    status = config.SENSOR_STATUS_WARNING if advice else config.SENSOR_STATUS_OK
    return status, advice


def is_stale(reading_timestamp):
    """True if we haven't heard from the ESP32 recently (or ever)."""
    if reading_timestamp is None:
        return True
    return (time.time() - reading_timestamp) > config.SENSOR_STALE_AFTER_SECONDS


def combine_with_leaf_result(sensor_reading, leaf_result):
    """Merge sensor advice with the leaf model's advice into one list.

    Both inputs may be falsy/empty (e.g. no capture yet, or ESP32 never
    connected) -- this degrades gracefully rather than erroring.
    """
    combined_advice = []

    if leaf_result and leaf_result.get("recommendation"):
        combined_advice.append(leaf_result["recommendation"])

    if sensor_reading and sensor_reading.get("has_reading") and not is_stale(
        sensor_reading.get("timestamp")
    ):
        _, sensor_advice = classify_reading(
            sensor_reading.get("moisture_raw"),
            sensor_reading.get("temperature_c"),
            sensor_reading.get("humidity_pct"),
        )
        combined_advice.extend(sensor_advice)

        # Cross-signal warning: humid air + an active disease detection
        # is a meaningfully worse combination than either signal alone,
        # since blight spreads fastest in humid conditions.
        humidity = sensor_reading.get("humidity_pct")
        if (
            leaf_result
            and leaf_result.get("status") == config.STATUS_DISEASE_DETECTED
            and humidity is not None
            and humidity >= config.HUMIDITY_HIGH_PCT
        ):
            combined_advice.append(
                "High humidity plus an active disease detection -- "
                "conditions favor rapid spread. Act now."
            )

    return combined_advice
