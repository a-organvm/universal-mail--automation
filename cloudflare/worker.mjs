const PROTECTED = new Set(["courts.ca.gov", "chase.com", "1password.com"]);

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

function senderCheck(sender) {
  const value = String(sender || "").trim().toLowerCase();
  if (!value) {
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
          keep_in_inbox: false,
          star: false,
        },
        is_vip: false,
        vip_note: "",
      },
    };
  }

  if (value.includes("courts.ca.gov") || value.endsWith(".gov")) {
    return {
      sender,
      protected: true,
      categorization: {
        label: "Personal/Government",
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
      },
    };
  }

  if (value.includes("chase.com")) {
    return {
      sender,
      protected: true,
      categorization: {
        label: "Finance/Banking",
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
      },
    };
  }

  const marketing = value.includes("deal") || value.includes("news");
  return {
    sender,
    protected: value.includes("chase.com") || value.includes("1password.com"),
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
      const runId = url.pathname.split("/").pop() || "demo";
      return json({
        run_id: runId,
        receipt: `Signed receipt for ${runId}`,
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
