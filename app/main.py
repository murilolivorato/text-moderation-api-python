import json
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request

from natural_language import GoogleNaturalLanguage

# Where to write the moderation log. Defaults to /logs/analyze.log, a volume
# mounted to ./logs on the host (see docker-compose.yml).
LOG_FILE = os.environ.get("LOG_FILE", "/logs/analyze.log")

logger = logging.getLogger("nlp")
logger.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# Console (visible via `docker compose logs`).
_console = logging.StreamHandler()
_console.setFormatter(_formatter)
logger.addHandler(_console)

# Persistent file (rotates at 5 MB, keeps 5 backups).
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    _file = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    _file.setFormatter(_formatter)
    logger.addHandler(_file)
except OSError as exc:  # pragma: no cover - log dir not writable, fall back to console only
    logger.warning("Could not open log file %s: %s", LOG_FILE, exc)

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify({"message": "Welcome to the Google Natural Language API", "status": "running"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/moderate", methods=["POST"])
def moderate():
    """
    Send JSON {"text": "..."} (via Postman) to run the three Natural Language
    evaluations of the text-moderation flow:

      - sentiment  (status / score / magnitude)
      - syntax     (level / status)
      - moderation (status / score / categories)

    The combined result is logged server-side and returned to the client.
    """
    body = request.get_json(silent=True)
    if not body or "text" not in body:
        return jsonify({"error": "Request body must be JSON with a 'text' field."}), 400

    text = str(body["text"]).strip()
    if not text:
        return jsonify({"error": "'text' must not be empty."}), 400

    logger.info("Received text (%d chars) for moderation", len(text))

    # Run each evaluation and collect the combined moderation log.
    moderation_log = {}
    try:
        nlp = GoogleNaturalLanguage()

        sentiment = nlp.evaluate_sentiment(text)
        moderation_log["sentiment_score"] = sentiment["score"]
        moderation_log["sentiment_magnitude"] = sentiment["magnitude"]
        moderation_log["sentiment_status"] = sentiment["status"]

        syntax = nlp.evaluate_syntax(text)
        moderation_log["syntax_level"] = syntax["level"]
        moderation_log["syntax_status"] = syntax["status"]

        moderate_text = nlp.evaluate_moderation(text)
        moderation_log["moderate_text_status"] = moderate_text["status"]
        moderation_log["moderate_text_score"] = moderate_text["score"]
        moderation_log["moderate_text_categories"] = moderate_text["categories"]
    except Exception as exc:  # noqa: BLE001 - surface auth/config/API errors to the client
        logger.exception("Natural Language request failed")
        return jsonify({"error": f"Natural Language request failed: {exc}"}), 500

    payload = {"text": text, "moderation_log": moderation_log}

    # One-line summary, then the full JSON (same as the client receives).
    logger.info(
        "Moderated text: sentiment=%s syntax=%s moderation=%s",
        moderation_log["sentiment_status"],
        moderation_log["syntax_status"],
        moderation_log["moderate_text_status"],
    )
    logger.info("Full response:\n%s", json.dumps(payload, ensure_ascii=False, indent=2))

    return jsonify(payload)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
