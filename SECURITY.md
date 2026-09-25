# Security Policy

## Reporting

Please avoid opening a public issue for a suspected vulnerability. Contact the repository owner privately through GitHub instead.

## Secrets

This repository does not require production secrets to be committed. Use environment variables for Flask session secrets and payment configuration. The provided `.env.example` contains placeholders only.

## Portfolio scope

GearShift Systems is a portfolio/learning application and has not been represented as a production payment-processing platform. The PayPal integration is sandbox-oriented. Production deployment would require additional controls including CSRF protection, authentication/authorization, hardened session/cookie settings, migrations, production database configuration, and a full payment-security review.
