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
- SQLite for development data storage
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

`User Voice Input -> Vapi Assistant -> Django API -> Database -> Response -> Spoken Reply`

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

| Phone Number | Name | Status |
| --- | --- | --- |
| `9866412176` | Raghav Panthi | active |
| `9857654321` | Sadhana Neupane | active |
| `9801112233` | Ramesh Thapa | inactive |

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
- Call page: [http://127.0.0.1:8000/call/](http://127.0.0.1:8000/call/)
- Dashboard: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- Code map: [http://127.0.0.1:8000/code-map](http://127.0.0.1:8000/code-map)

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

## Code Map

The `/code-map` page provides a visual explanation of:

- system architecture
- module structure
- backend service flow
- voice tool integration flow

A downloadable SVG architecture diagram is also included at `static/docs/code-map.svg`.

## Tools and Platforms Used

- Django
- SQLite
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

## Demo Video

A 3-5 minute demo video should be recorded separately for submission. It should show:

- the home page
- the call page
- the dashboard
- the code map page
- one sample API/tool flow

## Running Tests

Run the Django test suite:

```bash
python manage.py test
```

## Contributing

- Use the existing project structure to add features: `accounts`, `support`, `faq`, `core`.
- Please open issues or PRs with clear reproduction steps and the target branch `main`.

## GitHub And Vercel Deploy

1. Make sure the repo is clean locally and the virtual environment plus SQLite file are ignored.
2. Commit the code changes and push to GitHub.
3. Import the GitHub repo into Vercel.
4. Vercel will use `api/index.py` and `vercel.json` to serve the Django app.
5. Set secrets such as `SECRET_KEY` and any Vapi keys in the Vercel project settings.

If you want the deployed site to use different hostnames, set `ALLOWED_HOSTS` in Vercel to include them.

## License

This repository does not include an explicit license file. If you plan to publish or share this project, add a `LICENSE` file (for example MIT or Apache-2.0) to clarify reuse terms.

## Submission Checklist

- GitHub repository: this project workspace
- README with setup instructions: included
- Short explanation of how the assistant works: included above
- Tools/platforms used: included above
- Challenges faced during development: included above
- Demo video (3-5 minutes): still needed as a separate recording

## Notes

AwajAI supports bilingual conversations in English and Nepali, dynamically adapting responses based on user input language to improve accessibility for Nepalese telecom customers.
