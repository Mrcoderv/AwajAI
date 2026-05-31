# AwajAI

AwajAI is a Django-based voice-first customer support assistant for telecom use-cases. It provides a lightweight webhook and JSON APIs designed to integrate with voice platforms (for example Vapi) and supports short, conversational responses in English and Nepali.

## What the system does

AwajAI can:

- greet callers naturally
- answer simple telecom questions
- look up mock customer accounts by phone number
- fetch package details
- search FAQ answers
- maintain short conversational flow with some follow-up questions
- respond in English or Nepali based on the user

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


## How It Works

Voice flow:

`User Voice Input -> Vapi Assistant -> Django API -> Database {json template}-> Response -> Spoken Reply`

Tool flow:

`User Voice Input -> Vapi Assistant -> Django API Tool Call -> JSON Response -> Spoken Back to User`


## Sample Mock Accounts

These test accounts are seeded in `data/customers.json` so evaluators can try the app immediately.

| Phone Number   | Name            | Status   |
| -------------- | --------------- | -------- |
| `9866412176` | Raghav Panthi   | active   |
| `9857654321` | Sadhana Neupane | active   |
| `9801112233` | Ramesh Thapa    | inactive |

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
## Running Tests

Run the Django test suite:

```bash
python manage.py test
```


## Notes

AwajAI supports bilingual conversations in English and Nepali, dynamically adapting responses based on user input language to improve accessibility for Nepalese telecom customers.
