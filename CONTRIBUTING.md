# Contributing

Thanks for taking an interest in GearShift Systems.

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and use development-only credentials.
4. Run `python -m unittest discover -s tests -v` before submitting changes.

## Development guidelines

- Keep business logic readable and small enough to test.
- Preserve inventory consistency when changing order or receiving workflows.
- Never commit secrets, local databases, generated outbox files, IDE metadata, or Python bytecode.
- Add or update tests when changing behavior.
- Prefer focused commits with descriptive messages.

## Pull requests

A useful pull request explains:

- the problem being solved,
- the implementation approach,
- how the change was verified,
- any data-model or deployment impact.
