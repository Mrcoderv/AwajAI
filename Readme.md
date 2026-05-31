# AwajAI

AwajAI is a Django-based voice-first customer support assistant for telecom use-cases. It provides a lightweight webhook and JSON APIs designed to integrate with voice platforms (for example Vapi) and supports short, conversational responses in English and Nepali.

## What the system does

AwajAI can:

- greet callers naturally
- answer simple telecom questions
- look up mock customer accounts by phone number
- fetch package details
- search FAQ answers
- maintain short conversational flow with follow-up questions
- respond in English or Nepali based on the user
- show the architecture directly in the `/code-map` SVG page

## Tech Stack

- Django for backend and template-based frontend
- HTML/CSS for the UI
- Vapi-ready voice assistant flow
- JSON APIs for tool integration

## Project Structure

- `accounts` - customer data and account lookup logic
- `support` - conversation flow support and assistant-facing behavior
- `faq` - FAQ knowledge-base models and search logic
- `core` - shared utilities, frontend pages, and architecture views
- `static/docs/code-map.svg` - reusable SVG architecture diagram for the code map page

## How It Works

Voice flow:

`User Voice Input -> Vapi Assistant -> Django API -> Database {json template}-> Response -> Spoken Reply`

Tool flow:

`User Voice Input -> Vapi Assistant -> Django API Tool Call -> JSON Response -> Spoken Back to User`

## Key Features

- voice assistant prompt designed for telecom support
- bilingual English/Nepali behavior
- one-question-at-a-time conversation style
- account lookup by phone number
- package lookup by id or name
- FAQ search with short voice-friendly answers
- code map page for system design explanation
- dashboard page for viewing customer data

## Sample Mock Accounts

These test accounts are seeded in `data/customers.json` so evaluators can try the app immediately.

| Phone Number   | Name            | Status   |
| -------------- | --------------- | -------- |
| `9866412176` | Raghav Panthi   | active   |
| `9857654321` | Sadhana Neupane | active   |
| `9801112233` | Ramesh Thapa    | inactive |

## Frontend Pages

- `/` - home page
- `/chat/` - chat-first assistant page with optional voice mode
- `/call/` - legacy alias for the chat-first assistant page
- `/dashboard/` - customer info dashboard
- `/code-map` - architecture and system flow visualization

## API Endpoints

These endpoints are structured for voice assistant tools and return JSON responses.

- `/api/check-account` - customer lookup by phone number
- `/api/telconnect-account` - verified mock plan, balance, and due-date lookup
- `/api/package` - package details by id or name
- `/api/faq` - FAQ search
- `/api/session-phone` - conversational memory (stores verified phone in Django session)

## Vapi Webhook

To support a real Vapi voice agent, the repo exposes a webhook endpoint that Vapi can call during a call:

- `POST /api/vapi-webhook`

### What it expects

A JSON body containing a transcript of the latest user speech/text.

Common keys supported by this handler:

- `transcript`, `text`, `utterance`, `message`

### What it returns

A JSON response with:

- `reply`: the assistant text to speak back
- `language`: best-effort `en` or `ne`
- optional `data` for debugging (`account` / `package` / `faq`)

### Wiring note

This webhook uses the existing mock lookup logic (account/package/FAQ) already implemented in `accounts/services.py`, `core/services.py`, and `faq/services.py`.

### Implementation & testing

- Location: the webhook handler is implemented in `awaj_ai/vapi_views.py` and wired in `awaj_ai/urls.py` as `path("api/vapi-webhook", vapi_webhook, name="vapi_webhook")`.
- What it expects: a JSON `POST` with a transcript field such as `transcript`, `text`, or `utterance`.
- Example curl test (local server):

```bash
# basic transcript test
curl -s -X POST http://127.0.0.1:8000/api/vapi-webhook \
	-H "Content-Type: application/json" \
	-d '{"transcript":"Check account for 9866412176"}' | jq
```

The webhook will return JSON similar to:

```json
{
	"ok": true,
	"reply": "Thanks. I found the account for Raghav Panthi. Would you like your balance, due date, or package details next?",
	"language": "en",
	"data": { "account": { /* account payload */ } }
}
```

If you want the webhook to return only a short `reply` string for a voice engine that expects that shape, the handler already returns `reply` in the top-level JSON. Adjust payload parsing in `awaj_ai/vapi_views.py` if your Vapi configuration sends different key names.

## Quick Start

1. Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Apply migrations and load example data (if needed):

```bash
python manage.py migrate
# optionally seed example data (data/*.json or custom fixtures)
```

4. Run the development server:

```bash
python manage.py runserver
```

Open the app in your browser:

- Home: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Example Data Flow

1. A user says their phone number.
2. Vapi sends the request to Django.
3. Django checks the account, package, or FAQ data.
4. JSON is returned to the voice assistant.
5. The assistant speaks the short answer back to the caller.

## Prompt Design

The system prompt in `prompts/awajai_system_prompt.md` defines:

- natural telecom-style behavior
- short replies
- one question at a time
- phone-number-first account lookup
- interruption handling
- bilingual English/Nepali response behavior
- memory and conversational continuity

## Tools and Platforms Used

- Django
- Vapi-ready voice assistant flow
- Django templates
- JSON-based backend tool endpoints

## Challenges Faced

- keeping responses short while still being useful for voice support
- separating API logic into services for cleaner architecture
- supporting bilingual English/Nepali behavior naturally
- making the project understandable to non-technical reviewers
- designing a visual code map for system explanation
- handling Vapi webhook timing while keeping assistant response latency low

## Running Tests

Run the Django test suite:

```bash
python manage.py test
```

## Contributing

- Use the existing project structure to add features: `accounts`, `support`, `faq`, `core`.
- Please open issues or PRs with clear reproduction steps and the target branch `main`.

## License

This repository does not include an explicit license file. If you plan to publish or share this project, add a `LICENSE` file (for example MIT or Apache-2.0) to clarify reuse terms.

## Notes

AwajAI supports bilingual conversations in English and Nepali, dynamically adapting responses based on user input language to improve accessibility for Nepalese telecom customers.
