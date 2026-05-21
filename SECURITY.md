# Security Notes

Freshdesk Local Exporter is intended for local use. The desktop app and
development backend bind to loopback addresses by default so ticket data and
Freshdesk credentials stay on the machine running the app unless the user
explicitly exports data or changes the network configuration.

## Credentials

- Freshdesk API keys are kept in backend process memory for the current session.
- The browser or WebView cookie stores an opaque session ID, not the API key.
- Do not commit real `.env` files, credentials, logs, or local runtime folders.

## Exports

Exports and manifests can contain sensitive Freshdesk ticket data, contact
details, ticket conversations, account domains, filter values, and search
queries. Treat exported XLSX, Markdown, and manifest files as customer data.

The default `exports/` directory is ignored by Git. Review any custom export
directory before sharing files or publishing repository changes.

## Reporting

If you find a security issue in this project, avoid posting sensitive details in
a public issue. Contact the repository maintainer through a private channel when
one is available.
