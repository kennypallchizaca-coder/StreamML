# Security policy

## Supported configuration

The supported deployment is the current `main` branch using the pinned model
release, Docker Compose configuration and environment examples in this
repository. Do not expose OBS WebSocket, the MediaMTX control listeners or an
unprotected `.env` file to the public internet.

## Reporting a vulnerability

Do not include credentials, stream keys, personal data or exploit details in a
public issue. Use GitHub's private vulnerability-reporting feature for this
repository when it is enabled; otherwise contact a maintainer through the
repository owner profile and provide only the minimum information needed to
establish a secure channel.

If a credential may have been exposed, rotate it immediately. Removing it from
the latest commit does not remove it from Git history.

## Repository safeguards

- `.env`, keys, credentials, runtime databases, caches and raw downloads are
  ignored by Git and excluded from the Docker build context.
- `scripts/check_no_secrets.py --history` checks reachable Git history for
  common private-key and token signatures without echoing candidate values.
- CI executes the guard before builds are accepted. It supplements secret
  management and GitHub secret scanning; it is not a substitute for either.
