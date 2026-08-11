# Media Downloader Project Rules

Last updated: 2026-08-12 01:37:51 CST

## Required development order

1. Create or update a timestamped Markdown product/technical document in `docs/` before implementation.
2. Record the release validation matrix and expected evidence before implementation.
3. Write or update failing automated tests before changing downloader behavior.
4. Implement the smallest change that satisfies the documented requirements.
5. Run unit tests and static checks.
6. Perform live downloads with independently sourced public URLs for every affected platform.
7. Verify each downloaded media file with `ffprobe`; parsing metadata alone is not a pass.
8. Update the original timestamped validation document with actual backend, file properties, result, and failure notes.
9. Update `CHANGELOG.md` with an exact CST timestamp.
10. Commit, push, and publish the release artifacts to GitHub.

For maintenance releases, re-run every affected platform plus one unaffected smoke-test platform. Refresh a
live-validation URL when it becomes private, deleted, age-gated, or otherwise stops representing a normal public post.

## Evidence standard

- Do not mark a platform supported until a real public URL produces a playable media file.
- Record the test URL, test time, backend, output filename, byte size, duration, codecs, and dimensions or sample rate.
- If a backend fails, record the error and move to a different maintained backend. Do not loop on the same failed approach.
- Keep live tests separate from deterministic unit tests. Unit tests must not require third-party network services.
- Never commit downloaded media files, browser cookies, API keys, access tokens, or signed URLs.

## Documentation and release policy

- Every file under `docs/` must include `Created` and `Last updated` timestamps with timezone.
- Every release section in `CHANGELOG.md` must include an exact timestamp with timezone.
- Use semantic versions and Git tags.
- Update docs and changelog in the same commit as the related release.
- Treat a release as incomplete until the GitHub push and tag are visible remotely.

## Safety and legal boundaries

- Support public or user-authorized media only.
- Do not add DRM, paywall, private-content, or access-control bypasses.
- Browser cookie access requires explicit user authorization and must never be the silent default.
- Redact secrets and signed query strings from logs and validation documents.
- Prefer source-page parsing and self-hostable open-source backends over opaque hosted services.

## Code quality

- Keep platform adapters isolated behind a common interface.
- Validate remote URLs and downloaded content types before saving.
- Use atomic temporary files and rename only after validation succeeds.
- Preserve the legacy `video-downloader` command shape where practical.
- Maintain Python 3.9+ compatibility unless a timestamped design document approves a version change.
