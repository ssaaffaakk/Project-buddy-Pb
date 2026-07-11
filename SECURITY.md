# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report it privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
(the **Security → Report a vulnerability** tab on the repository), or email the
maintainer at the address listed on the GitHub profile.

Please include:

- a description of the issue and its impact,
- steps to reproduce (a proof of concept if possible),
- the affected version or commit.

You can expect an acknowledgement within a few days. Please give us a
reasonable window to release a fix before any public disclosure.

## Scope and hardening

ProjectBuddy already applies a number of defensive measures:

- CSRF protection on state-changing routes (Flask-WTF), with the JSON API
  gated by JWTs instead;
- a Content-Security-Policy, HSTS, `X-Content-Type-Options`, `X-Frame-Options`,
  Cross-Origin-Opener/Resource policies, and a restrictive Permissions-Policy;
- server-side authorization on every project/group/message action;
- rate limiting on authentication and expensive AI/search endpoints;
- secrets sourced only from environment variables (never committed).

Known limitations and planned hardening are tracked in the white paper
([`docs/WHITEPAPER.md`](docs/WHITEPAPER.md), "Limitations and Future Work").
