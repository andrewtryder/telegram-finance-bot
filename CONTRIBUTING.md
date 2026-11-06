# Contributing to Telegram Finance Bot

Thank you for your interest in contributing! Please review the guidelines below to ensure a smooth development process.

## Setup Instructions

1. Clone the repository and navigate into it:
   ```bash
   git clone https://github.com/andrewtryder/telegram-finance-bot.git
   cd telegram-finance-bot
   ```

2. Install [uv](https://docs.astral.sh/uv/) and sync production and
   development dependencies:
   ```bash
   uv sync --locked
   ```

## Development and Coding Standards

### Linting and Formatting

We use [Ruff](https://github.com/astral-sh/ruff) to enforce code formatting and style.

- Check for lint errors:
  ```bash
  uv run --locked ruff check .
  ```
- Run formatting check:
  ```bash
  uv run --locked ruff format --check .
  ```
- Automatically fix simple lint errors:
  ```bash
  uv run --locked ruff check --fix .
  uv run --locked ruff format .
  ```

### Running Tests

We use `pytest` for unit testing:
```bash
uv run --locked python -m pytest tests/
```

Before submitting a PR, make sure all tests pass and that you write tests for any new features or bug fixes.

## Conventional Commits

PR titles and commit messages should follow the [Conventional Commits](https://www.conventionalcommits.org/) format. Release Please uses these messages to determine the next semantic version and generate changelog entries.

Examples:
- `feat: add new /stockinfo command`
- `fix: resolve escaping issue in HTML parsing`
- `perf: cache provider responses`
- `docs: clarify Railway deployment`
- `chore: update dependencies`

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
