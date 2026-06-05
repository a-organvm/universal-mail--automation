// Protected-sender domains — parity with core/rules.py EXAMPLE_PROTECTED_SENDERS.
// The gate FAILS CLOSED and matches on a domain/subdomain BOUNDARY (never a raw
// substring), so 'purchase.com' never matches 'chase.com' and
// 'courts.ca.gov.evil.com' never matches a .gov rule.
const PROTECTED = [
  "docusign.net", // e-signature (legal docs)
  "irs.gov", "ssa.gov", "studentaid.gov", "login.gov", // US government (also via .gov rule)
  "apple.com", "appleid.com",
  "google.com", "accounts.google.com", "anthropic.com",
  "1password.com", "meta.com", "facebookmail.com",
  "chase.com",
  "example-lawfirm.com",
  "example-bank.com", "alerts.example-bank.com",
  "example-nonprofit.org",
];
// Subset routed to the Finance/Banking critical bucket.
const FINANCE = ["chase.com", "example-bank.com", "alerts.example-bank.com"];

// Boundary match: equality OR proper subdomain. Kills substring embeds
// ('purchase.com' != 'chase.com') and left-label spoofs.
function domainMatches(domain, entry) {
  return domain === entry || domain.endsWith("." + entry);
}

// US .gov only, anchored to the TERMINAL label of the recovered domain:
// 'irs.gov' -> true; 'irs.gov.attacker.com' -> false; 'service.gov.uk' -> false.
function govProtected(domain) {
  return domain.length > 0 && domain.split(".").pop() === "gov";
}

function isProtectedDomain(domain) {
  if (!domain) return false;
  if (govProtected(domain)) return true;
  return PROTECTED.some((entry) => domainMatches(domain, entry));
}

// Strip RFC-5322 CFWS comments "(...)" (innermost first, bounded) so a domain
// comment like 'irs(x).gov' collapses to 'irs.gov' the way the production engine's
// parser (email.utils.getaddresses) recovers it — rather than truncating to 'irs'.
function stripComments(s) {
  let out = String(s);
  for (let i = 0; i < 8; i++) {
    const next = out.replace(/\([^()]*\)/g, "");
    if (next === out) break;
    out = next;
  }
  return out;
}

// Recover the domain of EVERY address in the header (the UNION), regardless of
// separator (comma, semicolon, whitespace) or angle brackets, so a protected
// address listed ANYWHERE can't escape. A protected domain mentioned in a display
// name is also counted — that can only ADD protection (the safe direction).
// Plain-text only: unlike the production engine (core/rules.py) this demo gate
// does NOT MIME-decode (=?utf-8?..?=) or resolve iCloud relay local-parts; an
// undecodable header yields no address, so the caller FAILS CLOSED (held).
function senderDomains(sender) {
  const raw = stripComments(String(sender || "").toLowerCase());
  const domains = [];
  const re = /@([a-z0-9.-]+)/g; // the domain of each address, any separator/bracket
  let m;
  while ((m = re.exec(raw)) !== null) {
    const domain = m[1].replace(/\.+$/, ""); // strip trailing dot(s)
    if (domain) domains.push(domain);
  }
  return domains;
}

// True when the header can't be CLEANLY parsed into addresses: a domain split by
// folded/internal whitespace ('a@irs .gov'), or an '@' that can't be attached to a
// clean domain (stray '@', or folding WSP after '@'). The production engine would
// recover a possibly-protected sender from these, so this demo gate FAILS CLOSED
// on the ambiguity rather than archiving a truncated, non-matching fragment.
function headerIsAmbiguous(sender) {
  const raw = stripComments(String(sender || "").toLowerCase());
  const atCount = (raw.match(/@/g) || []).length;
  // A multi-address header with no comma is a malformed address list: the engine's
  // RFC parser (getaddresses) can't split it and fails closed, so we do too. (A
  // protected member is already matched before this point, so this only holds
  // genuinely-unprotected malformed headers — the safe direction.)
  if (atCount >= 2 && !raw.includes(",")) return true;
  let clean = 0;
  const re = /@([a-z0-9.-]+)/g;
  let m;
  while ((m = re.exec(raw)) !== null) {
    clean++;
    if (/^\s+\./.test(raw.slice(re.lastIndex))) return true; // 'irs .gov' (folded domain)
  }
  return atCount > clean; // an '@' with no cleanly-recoverable domain
}

const PLANS = [
  {
    id: "free",
    name: "Free / Self-host",
    price_cents: 0,
    price_display: "$0",
    monthly_run_cap: 50,
    providers: "gmail",
    retained_receipt_days: 0,
    blurb:
      "The full safety floor, free forever. Protected-sender gate + independent audit receipt, single provider, unlimited dry-runs.",
    features: [
      "Fail-closed protected-sender gate (always on)",
      "Independent, re-derivable audit receipt",
      "Unlimited dry-run / preview",
      "Gmail provider",
      "~50 live triage runs / month (unlimited self-hosted)",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price_cents: 1900,
    price_display: "$19/mo",
    monthly_run_cap: 5000,
    providers: "all",
    retained_receipt_days: 90,
    blurb:
      "All four providers, scheduled triage, downloadable + 90-day retained signed receipts.",
    features: [
      "Everything in Free",
      "All providers: Gmail, IMAP/iCloud, Outlook, Mail.app",
      "5,000 live triage runs / month",
      "Downloadable signed receipts + 90-day hosted ledger",
      "Scheduled / recurring triage + webhooks",
    ],
  },
  {
    id: "business",
    name: "Business",
    price_cents: 4900,
    price_display: "$49/mo",
    monthly_run_cap: null,
    providers: "all",
    retained_receipt_days: 365,
    blurb:
      "Unlimited runs, multi-mailbox, retained receipt history for compliance export, plus MCP + agent-commerce access.",
    features: [
      "Everything in Pro",
      "Unlimited triage runs",
      "Multi-mailbox / team, shared protected-sender policy",
      "1-year retained signed-receipt history (compliance export)",
      "MCP server access + ACP agent-commerce surface",
      "Priority support",
    ],
  },
];

const COMMON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "access-control-allow-headers": "content-type",
};

function json(body, init = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status || 200,
    headers: { ...COMMON_HEADERS, ...(init.headers || {}) },
  });
}

function text(body, init = {}) {
  return new Response(body, {
    status: init.status || 200,
    headers: { "content-type": "text/plain; charset=utf-8", ...(init.headers || {}) },
  });
}

// Tier-1 "Critical, held in inbox" categorization for a protected sender.
function protectedCategorization(label) {
  return {
    label,
    tier: 1,
    time_sensitive: true,
    tier_config: {
      number: 1,
      name: "Critical",
      color: "red",
      folder: "Action/Critical",
      keep_in_inbox: true,
      star: true,
    },
    is_vip: false,
    vip_note: "",
  };
}

function senderCheck(sender) {
  const domains = senderDomains(sender);

  // Protected if ANY recovered address is protected (union, matching the engine).
  const protectedDomain = domains.find(isProtectedDomain);
  if (protectedDomain) {
    let label = "Personal/Important";
    if (govProtected(protectedDomain)) label = "Personal/Government";
    else if (FINANCE.some((entry) => domainMatches(protectedDomain, entry))) label = "Finance/Banking";
    return { sender, protected: true, categorization: protectedCategorization(label) };
  }

  // FAIL CLOSED: no recoverable address, OR a header we can't cleanly parse (folded
  // whitespace in a domain, stray '@') that the engine might resolve to a protected
  // sender. Held in the inbox at low priority rather than archived.
  if (domains.length === 0 || headerIsAmbiguous(sender)) {
    return {
      sender,
      protected: true,
      categorization: {
        label: "Misc/Other",
        tier: 4,
        time_sensitive: false,
        tier_config: {
          number: 4,
          name: "Reference",
          color: "green",
          folder: null,
          keep_in_inbox: true, // fail closed: held because the sender is unidentifiable
          star: false,
        },
        is_vip: false,
        vip_note: "",
      },
    };
  }

  // Not protected -> ordinary demo categorization (subject/marketing heuristic unchanged).
  const value = String(sender || "").toLowerCase();
  const marketing = value.includes("deal") || value.includes("news");
  return {
    sender,
    protected: false,
    categorization: {
      label: marketing ? "Marketing" : "Misc/Other",
      tier: marketing ? 3 : 4,
      time_sensitive: false,
      tier_config: {
        number: marketing ? 3 : 4,
        name: marketing ? "Delegate" : "Reference",
        color: "amber",
        folder: null,
        keep_in_inbox: false,
        star: false,
      },
      is_vip: false,
      vip_note: "",
    },
  };
}

function triagePreview(provider, limit) {
  const capped = Number.isFinite(limit) && limit > 0 ? Math.min(limit, 50) : 50;
  const archived = capped > 0 ? 1 : 0;
  const protectedHeld = capped > 1 ? 2 : Math.max(0, capped - archived);
  return {
    dry_run: true,
    provider,
    receipt: `Triage receipt: ${Math.max(capped, 3)} message(s) — ${protectedHeld} protected held in inbox, ${archived} would leave inbox, 0 labeled-inbox, 0 kept.`,
    audit: {
      total: Math.max(capped, 3),
      protected_held: protectedHeld,
      archived,
      moved: 0,
      labeled: 0,
      kept: 0,
      violations: [],
    },
    processed: {
      processed_count: archived,
      success_count: archived,
      error_count: 0,
      label_counts: { Marketing: archived },
      errors: [],
    },
    run_id: "demo_preview",
  };
}

function billingPlans() {
  return {
    plans: PLANS.map((plan) => ({
      id: plan.id,
      name: plan.name,
      price_cents: plan.price_cents,
      price_display: plan.price_display,
      monthly_run_cap: plan.monthly_run_cap,
      providers: plan.providers,
      retained_receipt_days: plan.retained_receipt_days,
      blurb: plan.blurb,
      features: plan.features,
    })),
  };
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

async function serveApp(request, env) {
  const url = new URL(request.url);
  if (url.pathname === "/") {
    return Response.redirect(new URL("/app/", url), 302);
  }

  if (url.pathname === "/app" || url.pathname === "/app/") {
    const assetUrl = new URL("/index.html", url);
    return env.ASSETS.fetch(new Request(assetUrl, request));
  }

  return env.ASSETS.fetch(request);
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: COMMON_HEADERS });
    }

    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({ status: "ok", service: "universal-mail-automation", version: "0.1.0" });
    }

    if (url.pathname === "/v1/senders/check" && request.method === "POST") {
      const body = await readJson(request);
      return json(senderCheck(body.sender));
    }

    if (url.pathname === "/v1/triage/preview" && request.method === "POST") {
      const body = await readJson(request);
      return json(triagePreview(body.provider || "demo", Number(body.limit)));
    }

    if (url.pathname === "/v1/triage" && request.method === "POST") {
      const body = await readJson(request);
      return json(triagePreview(body.provider || "demo", Number(body.limit)));
    }

    if (url.pathname === "/v1/billing/plans" && request.method === "GET") {
      return json(billingPlans());
    }

    if (url.pathname === "/v1/billing/checkout" && request.method === "POST") {
      return json({ detail: "billing is not configured on this share demo" }, { status: 503 });
    }

    if (url.pathname === "/v1/billing/portal" && request.method === "POST") {
      return json({ detail: "billing is not configured on this share demo" }, { status: 503 });
    }

    if (url.pathname === "/v1/billing/webhook" && request.method === "POST") {
      return json({ detail: "billing is not configured on this share demo" }, { status: 503 });
    }

    if (url.pathname.startsWith("/v1/audit/") && request.method === "GET") {
      // HONESTY (review U055): this share demo holds no signing key, so it
      // must never present a receipt as "Signed" — the live API returns
      // {signed_body, signature, algorithm: "HMAC-SHA256", verify} and an
      // auditing agent verifies the HMAC. The demo says so explicitly
      // (signed:false, signature:null) instead of shipping a label-only
      // trust claim. It also mirrors the live API's 404 on unknown run_ids
      // rather than fabricating a plausible receipt for ANY id.
      const runId = url.pathname.split("/").pop() || "demo";
      const DEMO_RUN_IDS = new Set(["demo", "demo_preview", "demo_local_preview"]);
      if (!DEMO_RUN_IDS.has(runId)) {
        return json(
          {
            detail:
              "receipt not found — this share demo only serves the sample " +
              "run ids (demo_preview); the live API serves real, " +
              "HMAC-SHA256-signed receipts for actual runs",
          },
          { status: 404 },
        );
      }
      return json({
        run_id: runId,
        demo: true,
        signed: false,
        signature: null,
        algorithm: null,
        receipt:
          `Demo receipt for ${runId} (UNSIGNED sample — the live API returns ` +
          `an HMAC-SHA256 signed_body + signature an auditor can verify)`,
        dry_run: true,
        provider: "demo",
        audit: {
          total: 3,
          protected_held: 2,
          archived: 1,
          moved: 0,
          labeled: 0,
          kept: 0,
          violations: [],
        },
        processed: {
          processed_count: 1,
          success_count: 1,
          error_count: 0,
          label_counts: { Marketing: 1 },
          errors: [],
        },
      });
    }

    if (url.pathname === "/llms.txt") {
      return text(
        [
          "# Universal Mail Automation",
          "- Health: /health",
          "- Sender check: /v1/senders/check",
          "- Triage preview: /v1/triage/preview",
          "- Pricing: /v1/billing/plans",
          "- Audit receipt: /v1/audit/{run_id}",
        ].join("\n"),
      );
    }

    return serveApp(request, env);
  },
};

// Named exports for unit testing the protected-sender gate. The Cloudflare
// Worker runtime only consumes the default export above; these are inert there.
export { senderCheck, senderDomains, isProtectedDomain, domainMatches, govProtected };
