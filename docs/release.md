# Release Process

This project uses [Release Please](https://github.com/googleapis/release-please) with Conventional Commits to manage versions, changelog entries, GitHub Releases, and release Docker image tags.

## Version files

The current baseline version is stored in three places so both humans and automation can find it:

- `version.txt`
- `pyproject.toml`
- `bot/__init__.py`

Do not edit these files manually for normal releases. Release Please updates them in its generated release PR.

## Commit conventions

Release Please derives the next semantic version from merged Conventional Commit messages:

- `fix:` -> patch release, for example `0.1.0` to `0.1.1`
- `feat:` -> minor release, for example `0.1.0` to `0.2.0`
- `feat!:`, `fix!:`, or a `BREAKING CHANGE:` footer -> breaking release

Because this project starts below `1.0.0`, breaking changes are configured to bump the minor version until the project reaches `1.0.0`.

The PR title linter accepts the common release-relevant types: `feat`, `fix`, `perf`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, and `revert`.

## How to cut a release

1. Merge normal feature and fix PRs into `main` with Conventional Commit-style titles.
2. The Release Please workflow opens or updates a release PR.
3. Review the generated version bump and `CHANGELOG.md` entry.
4. Merge the release PR when ready.
5. Release Please creates the GitHub Release and `vX.Y.Z` tag.
6. The release workflow publishes GHCR image tags for `X.Y.Z`, `X.Y`, and `X`.

The existing Docker publish workflow still publishes `latest` and SHA tags for pushes to `main`.

## Token note

The release workflow can run with the default `GITHUB_TOKEN`. If you want workflows to be triggered by Release Please-created PRs and tags, add a repository secret named `RELEASE_PLEASE_TOKEN` containing a fine-grained personal access token with contents and pull request permissions. The workflow will use that token automatically when it exists, and falls back to `GITHUB_TOKEN` otherwise.

## Bootstrap note

`release-please-config.json` includes a `bootstrap-sha` that starts automated release history after the current public-release hardening work. Once the first Release Please-generated release PR has been merged, that bootstrap setting can be removed if desired.
