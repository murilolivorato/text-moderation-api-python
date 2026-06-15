# Google Natural Language — Text Moderation

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

## Example

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

Import `postman_collection.json` into Postman to try it without curl.

## Layout

```
.
├── Dockerfile               # python:3.12-slim + gunicorn
├── docker-compose.yml       # port 5001, mounts keys/ and logs/
├── postman_collection.json
├── app/
│   ├── requirements.txt     # flask, gunicorn, google-cloud-language
│   ├── main.py              # routes: /, /health, /moderate
│   ├── natural_language.py  # GoogleNaturalLanguage service (the 3 evaluations)
│   └── enums.py             # status/level enums for the moderation log
├── keys/                    # service-account.json (git-ignored)
└── logs/                    # analyze.log (git-ignored)
```
