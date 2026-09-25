# Testing Strategy

GearShift Systems uses small, deterministic automated tests to protect the workflows most likely to create data-integrity problems.

## Test layers

### Application smoke tests

These verify that:

- the Flask application can be created,
- the health endpoint responds,
- the home page renders on a case-sensitive Linux filesystem,
- ORM objects can be written and read.

### Business workflow tests

These exercise state-changing behavior against a temporary SQLite database:

- cart checkout persists an order and decrements stock,
- purchase-order receiving increments inventory,
- received quantities are recorded,
- stock movement audit rows are created,
- purchase-order status moves to `RECEIVED` when all units arrive.

## Isolation

Each test creates its own temporary SQLite database and removes it afterward. This keeps local development data out of automated verification and makes CI repeatable.

## Run locally

```bash
python -m unittest discover -s tests -v
```

## CI

The same suite runs on GitHub-hosted Ubuntu runners using Python 3.11 and Python 3.12.
