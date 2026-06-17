# Text Moderation API with Google Cloud Natural Language, Flask & Docker

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue?style=flat-square&logo=python)](https://www.python.org/downloads/)
[![Flask 3.0](https://img.shields.io/badge/Flask-3.0-darkgreen?style=flat-square&logo=flask)](https://flask.palletsprojects.com/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-blue?style=flat-square&logo=docker)](https://www.docker.com/)
[![Google Cloud Natural Language](https://img.shields.io/badge/Google%20Cloud-Natural%20Language%20API-red?style=flat-square&logo=google-cloud)](https://cloud.google.com/natural-language)
[![NLP](https://img.shields.io/badge/NLP-Text%20Moderation-purple?style=flat-square)](https://en.wikipedia.org/wiki/Natural_language_processing)
[![Content Safety](https://img.shields.io/badge/Content-Safety-orange?style=flat-square)](https://en.wikipedia.org/wiki/Content_moderation)
[![Sentiment Analysis](https://img.shields.io/badge/Sentiment-Analysis-yellow?style=flat-square)](https://en.wikipedia.org/wiki/Sentiment_analysis)
[![License MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)


<div align="center">
  <img src="https://miro.medium.com/v2/resize:fit:700/1*kDXvNH_FvMyfC1FFmoiADg.png" alt="Text Moderation Flow" width="700">
</div>

---

**Read the full article on Medium:**

✍️ [https://medium.com/@murilolivorato/building-a-text-moderation-api-with-google-cloud-natural-language-flask-docker-4513bdd800b7](https://medium.com/@murilolivorato/building-a-text-moderation-api-with-google-cloud-natural-language-flask-docker-4513bdd800b7)

A small Flask API (Docker) that moderates a text through the Google Cloud
Natural Language API. For each text it runs three evaluations, logs the
combined result, and returns it.

## Flow


`POST /moderate` with `{ "text": "..." }` runs, in order:

1. **Sentiment** (`analyzeSentiment` → `evaluate_sentiment`) — averages the
   per-sentence scores into `positive` / `neutral` / `negative`, returning the
   document `score` and `magnitude`.
2. **Syntax** (`analyzeSyntax` → `evaluate_syntax`) — inspects sentence length
   and part-of-speech ratios to produce a `level` (low/medium/high) and a
   descriptive `status`.
3. **Moderation** (`moderateText` → `evaluate_moderation`) — counts moderation
   categories with confidence > 0.05 into a `status` (low/medium/high), a
   `score`, and the matched `categories`.

The result is written to both the console (`docker compose logs`) and a rotating
file at `./logs/analyze.log`.

---

## Examples — the full spectrum

### Good — `positive-sentiment (0.9)` / `low` moderation

<div align="center">
  <img src="https://cdn-images-1.medium.com/max/800/1*MmX6fqTEmTYJbvxruJ88qg.png" alt="Good example" width="700">
</div>

Glowing hotel review: sentiment **0.9**, **zero** concerning categories → publish freely.

```json
{
  "moderation_log": {
    "sentiment_score": 0.9,
    "sentiment_magnitude": 4.5,
    "sentiment_status": "positive-sentiment",
    "moderate_text_status": "low",
    "moderate_text_score": 0,
    "moderate_text_categories": []
  }
}
```

### Medium — `positive-sentiment (0.1)` / `low` moderation

<div align="center">
  <img src="https://cdn-images-1.medium.com/max/800/1*VqTgwF9MsTEP6vC5Vd896A.png" alt="Medium example" width="700">
</div>

Mixed phone review: sentiment **0.1** (borderline neutral), safe moderation → publish, but flag as balanced opinion.

```json
{
  "moderation_log": {
    "sentiment_score": 0.1,
    "sentiment_magnitude": 2.3,
    "sentiment_status": "positive-sentiment",
    "moderate_text_status": "low",
    "moderate_text_score": 0,
    "moderate_text_categories": []
  }
}
```

### Bad — `negative-sentiment (-0.6)` / `high` moderation

![Bad example](https://cdn-images-1.medium.com/max/800/1*Y8nYP-DVNI3ZtMrZRXCSkg.png)

Angry airline complaint: sentiment **-0.6**, **11** concerning categories → flag for review or auto-reject.

```json
{
  "moderation_log": {
    "sentiment_score": -0.6,
    "sentiment_magnitude": 3.4,
    "sentiment_status": "negative-sentiment",
    "moderate_text_status": "high",
    "moderate_text_score": 11,
    "moderate_text_categories": [
      "toxic", "insult", "death, harm & tragedy", "violent",
      "public safety", "health", "religion & belief", "war & conflict",
      "politics", "finance", "legal"
    ]
  }
}
```

---

## Setup

1. Drop your Google service-account JSON at `keys/service-account.json`.
   The account needs the **Cloud Natural Language API** enabled.
2. Build and start:

   ```bash
   docker compose up --build
   ```

   The API listens on `http://localhost:5001`.

## Endpoints

| Method | Path        | Body                | Description                       |
|--------|-------------|---------------------|-----------------------------------|
| GET    | `/`         | —                   | Welcome / status                  |
| GET    | `/health`   | —                   | Liveness probe                    |
| POST   | `/moderate` | `{ "text": "..." }` | Run the moderation flow, log it   |

## Quick test

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

Or import `postman_collection.json` into Postman and pick Good / Medium / Bad from the **Moderate** folder.

## Layout

```
.
├── Dockerfile               # python:3.12-slim + gunicorn
├── docker-compose.yml       # port 5001, mounts keys/ and logs/
├── postman_collection.json
├── tutorial.md              # full Medium-style walkthrough
├── app/
│   ├── requirements.txt     # flask, gunicorn, google-cloud-language
│   ├── main.py              # routes: /, /health, /moderate
│   ├── natural_language.py  # GoogleNaturalLanguage service (the 3 evaluations)
│   └── enums.py             # status/level enums for the moderation log
├── keys/                    # service-account.json (git-ignored)
└── logs/                    # analyze.log (git-ignored)
```


<div align="center">
  <h3>⭐ Star This Repository ⭐</h3>
  <p>Your support helps us improve and maintain this project!</p>
  <a href="https://github.com/murilolivorato/text-moderation-api-python/stargazers">
    <img src="https://img.shields.io/github/stars/murilolivorato/text-moderation-api-python?style=social" alt="GitHub Stars">
  </a>
</div>
