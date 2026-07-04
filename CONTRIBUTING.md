# Contributing to Telegram Stock Price Bot

Thank you for your interest in contributing! Please review the guidelines below to ensure a smooth development process.

## Setup Instructions

1. Clone the repository and navigate into it:
   ```bash
   git clone https://github.com/andrewtryder/telegram-stock-price-bot.git
   cd telegram-stock-price-bot
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install production and development dependencies:
   ```bash
   pip install -r requirements.txt -r requirements-test.txt
   ```

## Development and Coding Standards

### Linting and Formatting

We use [Ruff](https://github.com/astral-sh/ruff) to enforce code formatting and style.

- Check for lint errors:
  ```bash
  ruff check .
  ```
- Run formatting check:
  ```bash
  ruff format --check .
  ```
- Automatically fix simple lint errors:
  ```bash
  ruff check --fix .
  ruff format .
  ```

### Running Tests

We use `pytest` for unit testing. Set `PYTHONPATH=.` when running tests locally:
```bash
PYTHONPATH=. pytest tests/
```

Before submitting a PR, make sure all tests pass and that you write tests for any new features or bug fixes.

## Conventional Commits

Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) format. Example:
- `feat: add new /stockinfo command`
- `fix: resolve escaping issue in HTML parsing`
- `chore: update requirements.txt`

## Secret Safety

**DO NOT** commit real secrets, API keys, or tokens:
- Ensure your `.env` file is never added to Git (it is ignored via `.gitignore`).
- Use placeholders in `.env.example`.
- Ensure tests and CI workflows do not print or log real secrets.
