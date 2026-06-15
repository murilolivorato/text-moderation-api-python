# Building a Text Moderation API with Google Natural Language, Flask & Docker

*Analyze sentiment, syntax, and content safety of any text — in a clean, reproducible container you can spin up in seconds.*

---

## Why text moderation matters (and why Google Natural Language?)

Every platform that lets users type something — a marketplace listing, a review, a comment, a property description — eventually faces the same question: **is this text any good, and is it safe to publish?**

Doing this by hand doesn't scale. You need a service that can read a piece of text and tell you, programmatically:

- **How does it *feel*?** Is the tone positive, negative, or neutral? (Sentiment)
- **Is it well written?** Does it have real sentence structure, or is it word salad? (Syntax)
- **Is it safe?** Does it contain toxic, violent, or otherwise harmful content? (Moderation)

**Google Cloud Natural Language** answers all three. It's a battle-tested, pre-trained NLP API — no model training, no GPUs, no ML PhD required. You send text, you get structured insights back. It supports dozens of languages, understands entities and grammar, and ships with a dedicated `moderateText` endpoint that flags 16+ categories of harmful content.

In this tutorial we'll build a small but production-shaped **moderation API**: a Flask service, wrapped in Docker, that takes a piece of text and returns a single combined "moderation log". We'll cover **every decision** — why Docker, why each file exists, how the Google Console is configured — so you can reproduce it and adapt it to your own product.

Here's what we'll end up calling:

```bash
curl -X POST http://localhost:5001/moderate \
  -H "Content-Type: application/json" \
  -d '{"text": "The new release is fantastic. The team did an amazing job."}'
```

```json
{
  "text": "The new release is fantastic. The team did an amazing job.",
  "moderation_log": {
    "sentiment_score": 0.8,
    "sentiment_magnitude": 1.6,
    "sentiment_status": "positive-sentiment",
    "syntax_level": "low",
    "syntax_status": "Text appears to be syntactically correct",
    "moderate_text_status": "low",
    "moderate_text_score": 0,
    "moderate_text_categories": []
  }
}
```

---

## Part 1 — Configuring Google Natural Language in the Google Cloud Console

Before a single line of code runs, the API needs to exist and be authorized. This is the part most tutorials gloss over, so let's be precise.

### Step 1: Create (or pick) a project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the **project selector** at the top → **New Project**.
3. Give it a name (e.g. `natural-language-demo`) and create it.

Everything you do — APIs, billing, service accounts — lives inside this project.

### Step 2: Enable billing

The Natural Language API is **not free beyond a quota**, so the project must have a billing account attached. Google gives every account a generous free tier (the first 5,000 units/month per feature are free at the time of writing), which is more than enough for development.

- **Billing** → **Link a billing account** → attach a card.

> 💡 You won't be charged inside the free tier, but Google requires billing to be *enabled* to use the API at all.

### Step 3: Enable the Natural Language API

1. In the console search bar, type **"Cloud Natural Language API"**.
2. Open it and click **Enable**.

This flips on the `language.googleapis.com` service for your project. Without this, every request returns `403 PERMISSION_DENIED`.

### Step 4: Create a service account

A **service account** is a non-human identity your backend uses to authenticate. This is the right pattern for server-to-server calls (as opposed to OAuth, which is for end users).

1. **IAM & Admin** → **Service Accounts** → **Create Service Account**.
2. Name it something like `natural-language-api`.
3. Grant it a role. For Natural Language, **Cloud Natural Language API User** is enough. For a demo, **Owner** works but is overly broad — prefer least privilege.
4. Click **Done**.

### Step 5: Download the JSON key

1. Click your new service account → **Keys** tab → **Add Key** → **Create new key** → **JSON**.
2. A `.json` file downloads. **This is your credential.** Treat it like a password.

This file contains a `private_key`, a `client_email`, and the `project_id`. Our app will point the `GOOGLE_APPLICATION_CREDENTIALS` environment variable at it, and the Google client library does the rest.

> 🔒 **Never commit this file to git.** We'll see how the project keeps it out of version control.

---

## Part 2 — How I built the project (and why every piece exists)

The whole project is intentionally small. Here's the layout:

```
google_natural_laguage/
├── Dockerfile               # how the image is built
├── docker-compose.yml       # how the container runs (ports, volumes, env)
├── .dockerignore            # what to keep OUT of the image
├── .gitignore               # what to keep OUT of git
├── postman_collection.json  # ready-made requests to test with
├── app/
│   ├── requirements.txt     # Python dependencies
│   ├── main.py              # Flask app + routes
│   ├── natural_language.py  # the Google Natural Language wrapper
│   └── enums.py             # status/level value definitions
├── keys/                    # service-account.json lives here (git-ignored)
└── logs/                    # analyze.log is written here (git-ignored)
```

Let's walk through the **why** of each one.

### Why Docker at all?

Because "it works on my machine" is not a deployment strategy. Docker packages the **exact** Python version, the **exact** dependencies, and the run command into a single image. Anyone — a teammate, a CI pipeline, a production server — runs the same thing with one command. No "did you install Python 3.12? did you pip install the right google-cloud version?" The container *is* the environment.

### The Dockerfile — building the image

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "main:app"]
```

Every line earns its place:

- **`FROM python:3.12-slim`** — a small, official Python base. `slim` drops build tooling we don't need, keeping the image lean.
- **`WORKDIR /app`** — all subsequent commands run here; it's also where our code lands.
- **`COPY requirements.txt` *before* `COPY app/`** — this is the classic Docker layer-caching trick. Dependencies change rarely; code changes constantly. By copying and installing requirements **first**, Docker caches that expensive `pip install` layer and only re-runs it when `requirements.txt` actually changes. Edit your code and rebuild → the install is skipped → builds take seconds.
- **`--no-cache-dir`** — tells pip not to keep its download cache, shaving megabytes off the final image.
- **`EXPOSE 5000`** — documents the port the app listens on inside the container.
- **`CMD [... gunicorn ...]`** — **why gunicorn and not `flask run`?** Flask's built-in server is single-threaded and explicitly *not* for production. **Gunicorn** is a real WSGI server: `--workers 2` runs two worker processes so the API can handle concurrent requests. `--bind 0.0.0.0:5000` makes it reachable from outside the container (binding to `127.0.0.1` would trap it inside).

### docker-compose.yml — running the container

The Dockerfile says *how to build*; Compose says *how to run*.

```yaml
services:
  api:
    build: .
    ports:
      - "5001:5000"
    volumes:
      - ./app:/app
      - ./keys:/keys:ro
      - ./logs:/logs
    environment:
      - FLASK_ENV=development
      - GOOGLE_APPLICATION_CREDENTIALS=/keys/service-account.json
      - LOG_FILE=/logs/analyze.log
    restart: unless-stopped
```

The reasoning behind each setting:

- **`ports: "5001:5000"`** — maps host port **5001** to container port **5000**. Why 5001 on the host? So this project can run side by side with another service that already uses 5000. The container still listens on 5000 internally.
- **`volumes`** — these are the project's backbone:
  - **`./app:/app`** — mounts your source code *into* the running container. Edit a `.py` file on your machine and it's instantly reflected inside — no rebuild needed during development.
  - **`./keys:/keys:ro`** — mounts the credentials folder **read-only** (`:ro`). The app can read `service-account.json` but can never modify or delete it. The key never goes into the image — it's injected at runtime.
  - **`./logs:/logs`** — persists logs to your host. When the container stops, the logs survive.
- **`environment`** — configuration via env vars (the [12-factor](https://12factor.net/config) way):
  - **`GOOGLE_APPLICATION_CREDENTIALS`** — *the* magic variable. The Google client library automatically looks for it and authenticates using the file it points to. No keys hardcoded in source.
  - **`LOG_FILE`** — where the app writes its rotating log.
- **`restart: unless-stopped`** — if the container crashes, Docker brings it back automatically.

### .dockerignore and .gitignore — what to leave out

```
__pycache__/
*.pyc
.env
.git
keys/
logs/
```

- **`.dockerignore`** keeps junk (caches, `.git`, **your secret keys**) out of the build context, making images smaller and safer.
- **`.gitignore`** ensures `keys/` and `logs/` are **never committed**. Your service-account credential stays on your machine, full stop.

This is the single most important security decision in the project: **secrets are mounted at runtime, never baked into the image or pushed to git.**

### requirements.txt — the dependencies

```
flask==3.0.3
gunicorn==22.0.0
google-cloud-language==2.13.4
```

- **flask** — the minimal web framework for the routes.
- **gunicorn** — the production server (see Dockerfile rationale above).
- **google-cloud-language** — the official Google client. It handles auth, retries, and request/response serialization. Pinning **exact versions** (`==`) means the build is reproducible forever — no surprise breakage when a new release ships.

### natural_language.py — the brains

This is the wrapper around Google's API. It does three analyses and turns each raw response into a clean verdict.

```python
from google.cloud import language_v1, language_v2

class GoogleNaturalLanguage:
    LANGUAGE = "pt-BR"

    def __init__(self):
        self._v1 = language_v1.LanguageServiceClient()
        self._v2 = language_v2.LanguageServiceClient()
```

**Why two clients (v1 and v2)?** Google split features across API versions:

- **`analyzeSentiment`** and **`analyzeSyntax`** live in **v1**.
- **`moderateText`** — the newer content-safety endpoint — lives in **v2**.

So the class holds one client of each and routes calls accordingly. Notice we **never pass credentials** in code — `LanguageServiceClient()` reads `GOOGLE_APPLICATION_CREDENTIALS` from the environment by itself.

The three evaluation methods each follow the same shape: *call the API → interpret the numbers → return a labeled result.*

**1. Sentiment** — averages the per-sentence scores to decide an overall mood:

```python
def evaluate_sentiment(self, text):
    response = self.analyze_sentiment(text)
    sentiment = response.document_sentiment
    average = sum(s.sentiment.score for s in response.sentences) / len(response.sentences)

    if average > 0.1:
        status = GnlSentimentStatus.POSITIVE
    elif average < -0.1:
        status = GnlSentimentStatus.NEGATIVE
    else:
        status = GnlSentimentStatus.NEUTRAL

    return {"status": status.value,
            "score": round(sentiment.score, 4),
            "magnitude": round(sentiment.magnitude, 4)}
```

- **`score`** ranges from **-1.0 (negative)** to **+1.0 (positive)**.
- **`magnitude`** is the *strength* of emotion (how much emotional content there is, regardless of direction).

**2. Syntax** — inspects sentence length and part-of-speech ratios to judge writing quality. It returns a `level` (low/medium/high concern) and a human-readable `status` like *"Text appears to be syntactically correct"* or *"Text seems to lack verbs"*. This catches gibberish, keyword-stuffing, and broken grammar.

**3. Moderation** — counts how many harmful-content categories the text trips:

```python
def evaluate_moderation(self, text):
    response = self.moderate_text(text)
    moderation_score = 0
    concerning = []
    for category in response.moderation_categories:
        if category.confidence > 0.05:
            moderation_score += 1
            concerning.append(category.name.lower())
    # ... thresholds turn the count into low / medium / high
```

Google returns ~16 categories per request (toxic, insult, violent, sexual, etc.), each with a confidence. We flag the ones above a threshold and roll them up into a `low` / `medium` / `high` status.

> 🌐 **A note on language:** the wrapper pins the document language to `pt-BR`. If your content is in another language, change `LANGUAGE` (or remove it to let Google auto-detect). Forcing the wrong language skews the syntax/POS results.

### enums.py — meaningful, stable values

Instead of returning magic strings scattered through the code, all the status/level values live in one place:

```python
class GnlSentimentStatus(str, Enum):
    POSITIVE = "positive-sentiment"
    NEUTRAL = "neutral-sentiment"
    NEGATIVE = "negative-sentiment"
```

This makes the output **predictable** (the API always returns the same vocabulary) and the code **self-documenting**. If you later persist these to a database, the enum is your single source of truth.

### main.py — the web layer

The Flask app exposes three routes and ties everything together:

| Method | Path        | Purpose                         |
|--------|-------------|---------------------------------|
| GET    | `/`         | Welcome / status                |
| GET    | `/health`   | Liveness probe (for monitoring) |
| POST   | `/moderate` | The actual work                 |

The `/moderate` handler is deliberately defensive:

```python
@app.route("/moderate", methods=["POST"])
def moderate():
    body = request.get_json(silent=True)
    if not body or "text" not in body:
        return jsonify({"error": "Request body must be JSON with a 'text' field."}), 400

    text = str(body["text"]).strip()
    if not text:
        return jsonify({"error": "'text' must not be empty."}), 400

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
    except Exception as exc:
        logger.exception("Natural Language request failed")
        return jsonify({"error": f"Natural Language request failed: {exc}"}), 500

    payload = {"text": text, "moderation_log": moderation_log}
    logger.info("Full response:\n%s", json.dumps(payload, ensure_ascii=False, indent=2))
    return jsonify(payload)
```

Design decisions worth highlighting:

- **Validation first.** A missing or empty `text` returns a clean `400` *before* we ever call Google (and spend a quota unit).
- **Client construction is inside the `try`.** If the credentials file is missing or invalid, the error surfaces as tidy JSON (`500` with a message) instead of an ugly stack-trace HTML page. This was an actual bug I fixed — originally the client was built outside the try block and a missing key produced a raw Flask 500.
- **Everything is logged.** The combined result is written to both the console (visible via `docker compose logs`) and a **rotating file** (`logs/analyze.log`, 5 MB × 5 backups). You get an audit trail of every moderation decision for free.

---

## Part 3 — How to run and use it

### 1. Drop in your credential

Put the JSON key you downloaded from the console at:

```
keys/service-account.json
```

(That's the path `GOOGLE_APPLICATION_CREDENTIALS` points to inside the container.)

### 2. Build and start

```bash
docker compose up --build
```

Docker builds the image, installs dependencies, and starts gunicorn. The API is live at **http://localhost:5001**.

### 3. Confirm it's alive

```bash
curl http://localhost:5001/health
# {"status": "healthy"}
```

### 4. Moderate some text

```bash
curl -X POST http://localhost:5001/moderate \
  -H "Content-Type: application/json" \
  -d '{"text": "I highly recommend this incredible resort. It was the best vacation of my life!"}'
```

You'll get back sentiment, syntax, and moderation verdicts in one JSON object.

### 5. Or use Postman

Import `postman_collection.json` and you'll find a **Moderate** folder with three ready-made requests demonstrating the full spectrum:

| Request | Sentiment | Moderation |
|---|---|---|
| **Moderate Text – Good** (glowing hotel review) | `positive-sentiment` (0.9) | `low` |
| **Moderate Text – Medium** (mixed phone review) | `positive-sentiment` (0.1, borderline) | `low` |
| **Moderate Text – Bad** (angry airline complaint) | `negative-sentiment` (-0.6) | `high` (11 categories) |

Each comes with a saved example response, so you can see expected output even before sending.

---

## What you've built

In a couple hundred lines you now have a **content-moderation microservice** that:

- ✅ Reads any text and scores its **sentiment**, **syntax quality**, and **content safety**
- ✅ Runs identically on any machine thanks to **Docker**
- ✅ Keeps secrets out of git and out of the image
- ✅ Logs every decision for auditing
- ✅ Ships with a Postman collection for instant testing

### Where to take it next

- **Persist the moderation log** to a database so you can review flagged content later.
- **Auto-reject or auto-flag** submissions where `moderate_text_status == "high"`.
- **Add `analyzeEntities`** to extract names, places, and organizations from the text.
- **Multi-language support** by detecting language per request instead of pinning `pt-BR`.
- **Rate limiting and caching** to stay comfortably inside the free tier.

Google Natural Language turns "is this text okay?" from a hard ML problem into a single HTTP call. Wrapped in Docker, it becomes a building block you can drop into any product. Happy moderating! 🚀
