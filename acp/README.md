# Agentic Commerce Notes

The ACP surface intentionally uses a self-asserted bearer model for the current
Stripe Shared Payment Token flow: any non-empty `Authorization: Bearer ...`
value is treated as the buyer account key, and the gate creates or reuses the
matching account before session creation. This does not grant free credits
because `/complete` still requires a valid SPT charge, per-session Stripe
idempotency, request idempotency, and `fulfill_once` crediting; the abuse surface
is account/session creation and failed-payment traffic, so production deployments
should keep normal HTTP rate limits, body limits, and Stripe webhook monitoring
in front of `/acp/*`.
