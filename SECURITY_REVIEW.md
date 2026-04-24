# Security Review

Date: 2026-04-24

## Fixed in this pass

### High

- Hard-coded fallback secret key.
  The app previously accepted a predictable default `SECRET_KEY`. This made session forgery materially easier if the deployment was left unconfigured.
  Status: fixed by switching to environment-driven secrets with a random fallback and production-ready cookie settings.

- Missing CSRF protection on state-changing routes.
  Login, signup, inventory updates, deletions, uploads, wipe-data, checkout, refunds, and kitchen completion actions previously accepted cross-site POST requests without a CSRF token.
  Status: fixed with app-wide CSRF validation for form posts and JavaScript API posts.

### Medium

- Missing proxy-awareness for HTTPS deployments.
  Behind Cloudflare Tunnel or another reverse proxy, Flask needs trusted forwarded headers to correctly detect the original scheme and host.
  Status: fixed with `ProxyFix`.

- Unbounded upload size.
  Historical CSV upload had no explicit application-level size cap.
  Status: fixed with `MAX_CONTENT_LENGTH`.

- Input validation gaps.
  Several POST flows trusted empty names or non-positive quantities.
  Status: fixed with additional validation in inventory and checkout routes.

### Reliability defects found during review

- Recipe creation/edit used `manual_cost` instead of `manual_cost_input`.
  Status: fixed.

- Refund route used `datetime.timedelta` even though only `datetime` was imported.
  Status: fixed.

## Residual risks

### Medium

- No rate limiting on login or other sensitive endpoints.
  Brute-force resistance still depends on external controls. If the site is internet-facing, add rate limiting at Cloudflare and optionally application-side throttling.

- No account verification or password-reset flow.
  This is acceptable for internal use, but it is weak for public self-service registration.

### Medium to low

- SQLite is acceptable for a small deployment, but concurrent write load and operational recovery are limited compared with PostgreSQL.

- Forms do not currently enforce strong password policy beyond hashing. Password hashing is present, but minimum strength rules are not.

## Recommended Cloudflare controls

- Enable WAF managed rules.
- Add rate limiting on `/login` and `/signup`.
- Restrict admin access further with Cloudflare Access if this is an internal system.
- Keep the origin private and avoid opening inbound ports to the app container.
