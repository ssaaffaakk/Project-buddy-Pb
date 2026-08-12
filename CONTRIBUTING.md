# Contributing to ProjectBuddy

Thanks for your interest in improving ProjectBuddy. This guide covers the
local setup and the conventions the project follows.

Please note that this project follows a [Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating, you agree to abide by its terms.

## Development setup

**Prerequisites:** Python 3.11+ (production runs 3.11), Git, and optionally
Docker for the full stack.

```bash
# 1. Clone and create a virtualenv
python3 -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 3. Configure environment
cp .env.example .env        # then fill in the values (SECRET_KEY is required)

# 4. Initialize the database and run
flask db upgrade
flask run
```

The React explorer (feature-flagged) lives in `frontend/`:

```bash
cd frontend && npm install && npm run build
```

## Before you open a pull request

Run the same checks CI runs:

```bash
ruff check .            # lint
pytest --cov=.          # tests + coverage
```

- **Keep the test suite green.** New behavior needs a test; bug fixes need a
  regression test.
- **Match the surrounding style.** The project follows the conventions in
  [`CLAUDE.md`](CLAUDE.md) — application factory, blueprints in `routes/`,
  models in `models.py`, SocketIO for real-time, and the S3 storage
  abstraction for uploads.
- **Never commit secrets.** Configuration comes from `.env` (git-ignored);
  update `.env.example` when you add a new variable.
- **Migrations:** after changing models, run `flask db migrate -m "…"` and
  commit the generated migration.

## Commit and PR hygiene

- Write clear, imperative commit subjects (`fix: …`, `feat: …`, `docs: …`).
- Keep PRs focused on a single concern; describe what changed and how you
  verified it.
- Reference any related issue.

## Reporting bugs and requesting features

Use the GitHub issue templates. For security issues, follow
[`SECURITY.md`](SECURITY.md) instead of opening a public issue.
