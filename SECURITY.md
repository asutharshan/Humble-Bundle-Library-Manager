# Security Policy

## Supported version

| Version | Supported |
|---|---|
| 2.0.1 | Yes |
| 2.0.0 | Best effort |
| 1.x | Best effort only |

## Sensitive information

Do not publish:

- cookies;
- passwords;
- authentication tokens;
- API keys;
- private media URLs;
- customer information;
- personally identifiable information;
- secrets contained in logs.

## Browser cookies

Media Utility should never intentionally:

- upload browser cookies to a project-controlled server;
- write raw cookies to application logs;
- display authentication tokens in the UI;
- include credentials in crash reports.

## Reporting vulnerabilities

Use GitHub private security reporting where available.

If public reporting is unavoidable, redact all sensitive information.

A useful report should include:

- Media Utility version;
- Windows version;
- Python version;
- steps to reproduce;
- expected behaviour;
- actual behaviour;
- redacted logs.

## Dependency security

Keep dependencies current and review them before releases.

Downloaded media should be treated as untrusted content and should never be automatically executed.
