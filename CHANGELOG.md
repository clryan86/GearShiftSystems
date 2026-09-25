# Changelog

All notable portfolio-engineering improvements to this repository are documented here.

## Unreleased

### Added
- GitHub Actions CI across Python 3.11 and 3.12.
- Docker/Gunicorn runtime.
- Automated smoke and domain-workflow tests.
- Architecture documentation.
- Security and contribution guidance.
- Dependabot configuration.
- Structured issue and pull-request templates.

### Changed
- Runtime configuration now supports environment-driven `DATABASE_URL` and `SECRET_KEY`.
- Flask explicitly uses the repository's existing `Templates` directory for Linux portability.
- Repository documentation was rewritten for technical reviewers and recruiters.

### Removed
- Committed IDE metadata and Python bytecode/cache artifacts.
