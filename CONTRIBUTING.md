# Contributing to MATIKA

Thank you for your interest in improving this project.

## Getting started

1. Clone the repository and create a virtual environment (Python 3.12 recommended).
2. Install dependencies:

   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Copy `.env.example` to `.env` and adjust variables if needed.
4. Run migrations and optional demo data:

   ```bash
   python manage.py migrate
   python manage.py seed_demo
   ```

5. Run the test suite before submitting changes:

   ```bash
   pytest
   ruff check .
   python manage.py check
   ```

## Code style

- Follow existing patterns in the codebase (imports, naming, templates).
- Prefer small, focused changes tied to a single issue or feature.
- Do not commit secrets: use `.env` locally and keep `.env.example` updated when new settings are added.

## Pull requests

- Describe what changed and why in the PR description.
- Ensure tests pass and `ruff check .` is clean for touched files.
- For UI or scheduling logic changes, mention how you verified behavior (manual steps or automated tests).

## Translations

If you add user-visible strings, update `locale/` with `makemessages` / `compilemessages` as described in the README.

## Questions

Open a discussion or issue on the repository if something in the setup or architecture is unclear.
