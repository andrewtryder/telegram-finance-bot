# Contributing to Telegram Finance Bot

Thank you for your interest in contributing! Please review the guidelines below to ensure a smooth development process.

## Setup Instructions

1. Clone the repository and navigate into it:
   ```bash
   git clone https://github.com/andrewtryder/telegram-finance-bot.git
   cd telegram-finance-bot
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

PR titles and commit messages should follow the [Conventional Commits](https://www.conventionalcommits.org/) format. Release Please uses these messages to determine the next semantic version and generate changelog entries.

Examples:
- `feat: add new /stockinfo command`
- `fix: resolve escaping issue in HTML parsing`
- `perf: cache provider responses`
- `docs: clarify Railway deployment`
- `chore: update requirements.txt`

Release impact:
- `fix:` creates a patch release.
- `feat:` creates a minor release.
- `feat!:`, `fix!:`, or a `BREAKING CHANGE:` footer creates a breaking release.

Accepted PR title types are `feat`, `fix`, `perf`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, and `revert`.

## Release Process

Normal contributors do not need to edit version files manually. Release Please manages:

- `CHANGELOG.md`
- `version.txt`
- `pyproject.toml`
- `bot/__init__.py`
- GitHub Releases and `vX.Y.Z` tags

When enough release-worthy commits land on `main`, Release Please opens or updates a release PR. Maintainers should review the generated changelog and version bump, then merge the release PR to publish the release.

See [docs/release.md](docs/release.md) for the full release workflow.

## Secret Safety

**DO NOT** commit real secrets, API keys, or tokens:
- Ensure your `.env` file is never added to Git (it is ignored via `.gitignore`).
- Use placeholders in `.env.example`.
- Ensure tests and CI workflows do not print or log real secrets.
