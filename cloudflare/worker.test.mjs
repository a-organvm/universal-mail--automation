// Tests for the Cloudflare share-demo protected-sender gate.
// Run: node --test cloudflare/worker.test.mjs
//
// These lock in the fix for the substring-spoofable gate (review G15): the gate
// must FAIL CLOSED, parse the real address (display name never participates),
// match on a domain BOUNDARY (not substring), anchor .gov to the terminal label,
// and protect the UNION over a multi-address From header.
import { test } from "node:test";
import assert from "node:assert/strict";
import worker, {
  senderCheck,
  isProtectedDomain,
  govProtected,
  readJson,
} from "./worker.mjs";

const isProtected = (s) => senderCheck(s).protected;
const held = (s) => senderCheck(s).categorization.tier_config.keep_in_inbox;

test("protected senders are held (parity with EXAMPLE_PROTECTED_SENDERS)", () => {
  for (const s of [
    "a@irs.gov", "a@ssa.gov", "user@login.gov",
    "Some Court <clerk@courts.ca.gov>", // .gov terminal label
    "alerts@chase.com", "Statements <noreply@alerts.example-bank.com>",
    "a@apple.com", "x@accounts.google.com", "sec@1password.com",
    "a@anthropic.com", "a@docusign.net", "a@meta.com",
    "a@sub.chase.com", // proper subdomain
  ]) {
    assert.equal(isProtected(s), true, `expected protected: ${s}`);
    assert.equal(held(s), true, `expected held in inbox: ${s}`);
  }
});

test("substring / left-label spoofs are NOT protected (the G15 fix)", () => {
  for (const s of [
    "x@courts.ca.gov.evil.com", // includes 'courts.ca.gov' but terminal label is 'com'
    "x@irs.gov.attacker.com",
    "x@service.gov.uk", // non-US .gov
    "x@purchase.com", // contains 'chase.com' as a substring
    "x@notchase.com",
    "x@chase.com.evil.net",
    "x@my1password.com", // contains '1password.com'
    "x@example-bank-marketing.com", // sibling marketing domain, intentionally unprotected
  ]) {
    assert.equal(isProtected(s), false, `expected NOT protected: ${s}`);
  }
});

test("display name never participates in the decision", () => {
  // A protected domain in the display name must not protect a non-protected address.
  assert.equal(isProtected('"chase.com security" <a@evil.com>'), false);
  assert.equal(isProtected("irs.gov phishing <a@evil.com>"), false);
  // Conversely a real protected address inside <> IS protected.
  assert.equal(isProtected('"Marketing Deals" <a@irs.gov>'), true);
});

test("multi-address From is protected if ANY address is protected (union)", () => {
  assert.equal(isProtected("a@irs.gov, b@evil.com"), true);
  assert.equal(isProtected("b@evil.com, a@irs.gov"), true); // protected listed last
  assert.equal(isProtected("a@evil.com, b@spam.net"), false);
});

test("union holds for EVERY separator / bracket form (wa74x77mp data-loss fix)", () => {
  // Regression guard: the original fix split only on ',' and kept the last token,
  // so these all dropped the protected address and failed OPEN (data loss).
  for (const s of [
    "noreply@chase.com hi@evil.com",      // whitespace-separated
    "noreply@chase.com; ads@evil.com",    // semicolon + space
    "a@irs.gov;b@evil.com",               // semicolon, no space
    "a@chase.com b@evil.com",             // whitespace, protected first
    "noreply@chase.com <ads@evil.com>",   // bare protected addr then bracketed junk
    "a@irs.gov<b@evil.com>",
    "Display <a@chase.com> <b@evil.com>", // two bracketed addrs, protected first
    "List: noreply@chase.com; <ads@evil.com>", // RFC group syntax
    "x@evil.com, a@irs.gov b@evil.org",   // protected in the middle of a mixed list
  ]) {
    assert.equal(isProtected(s), true, `expected protected (union, any separator): ${s}`);
  }
  // None protected, well-formed (comma-separated) -> not protected.
  assert.equal(isProtected("a@evil.com, b@spam.net"), false);
});

test("malformed (comma-less) multi-address header fails closed, matching the engine", () => {
  // The RFC parser the engine uses (getaddresses) can't split a comma-less address
  // list and fails closed; the demo gate matches that for unprotected members.
  assert.equal(isProtected("a@evil.com b@spam.net"), true); // whitespace, no comma
  assert.equal(isProtected("a@evil.com; b@spam.net"), true); // semicolon, no comma
});

test("CFWS comment / folded whitespace in the domain doesn't lose protected mail", () => {
  // RFC-5322-legal domain comments + folding WSP. The engine recovers the real
  // domain; this gate either recovers it (comment strip) or fails closed (WSP).
  for (const s of [
    "a@irs(x).gov",
    "billing@irs(internal-routing).gov",
    "a@chase(x).com",
    "a@docusign(legal).net",
    "a@example-bank(alerts).com",
    "Name <a@irs(c).gov>",
    "Foo <a@evil.com>, Bar <b@irs(x).gov>", // protected member truncated by comment
    "a@irs(c).gov, x@evil.com",
    "a@irs .gov",   // folded / internal whitespace
    "a@irs\t.gov",
    "a@chase .com",
    "a@evil.com b@ irs.gov", // folding WSP after '@' on the protected member
    "a@evil.com, b@(c)irs.gov",
  ]) {
    assert.equal(isProtected(s), true, `expected protected (CFWS/WSP): ${JSON.stringify(s)}`);
  }
  // Comment stripping must NOT over-trigger on a clean, non-protected sender.
  assert.equal(isProtected("a@evil(x).com"), false); // -> evil.com, not protected
});

test("an email in the display name over-protects (safe direction)", () => {
  // The demo gate counts every @domain, so a protected domain mentioned anywhere
  // can only ADD protection. Plain text WITHOUT '@' never participates.
  assert.equal(isProtected('"statement a@chase.com" <a@evil.com>'), true);
  assert.equal(isProtected('"chase.com security" <a@evil.com>'), false);
});

test("fail closed: empty / unparseable senders are held", () => {
  for (const s of ["", "   ", null, undefined, "not-an-email", "no-at-sign", "<>"]) {
    assert.equal(isProtected(s), true, `expected fail-closed protected: ${JSON.stringify(s)}`);
    assert.equal(held(s), true, `expected held: ${JSON.stringify(s)}`);
  }
});

test("normalization: case + trailing dot", () => {
  assert.equal(isProtected("A@APPLE.COM"), true);
  assert.equal(isProtected("a@irs.gov."), true); // trailing root dot
  assert.equal(isProtected("  a@CHASE.com  "), true);
});

test("labels route correctly for protected senders", () => {
  assert.equal(senderCheck("a@irs.gov").categorization.label, "Personal/Government");
  assert.equal(senderCheck("a@chase.com").categorization.label, "Finance/Banking");
  assert.equal(senderCheck("a@1password.com").categorization.label, "Personal/Important");
});

test("ordinary (non-protected) categorization is preserved", () => {
  assert.equal(senderCheck("deals@shop.example").categorization.label, "Marketing");
  assert.equal(senderCheck("news@blog.example").categorization.label, "Marketing");
  const misc = senderCheck("someone@random.example");
  assert.equal(misc.protected, false);
  assert.equal(misc.categorization.label, "Misc/Other");
  assert.equal(misc.categorization.tier_config.keep_in_inbox, false);
});

test("route validation rejects malformed sender and provider input", async () => {
  const badSender = await worker.fetch(
    new Request("https://example.test/v1/senders/check", {
      method: "POST",
      body: JSON.stringify({ sender: "a@example.com\r\nbcc: victim@example.com" }),
    }),
    {},
  );
  assert.equal(badSender.status, 400);

  const badProvider = await worker.fetch(
    new Request("https://example.test/v1/triage/preview", {
      method: "POST",
      body: JSON.stringify({ provider: "../gmail", limit: 1 }),
    }),
    {},
  );
  assert.equal(badProvider.status, 400);
});

test("route validation rejects invalid JSON objects", async () => {
  await assert.rejects(
    readJson(
      new Request("https://example.test/v1/senders/check", {
        method: "POST",
        body: "[1,2,3]",
      }),
    ),
    /JSON body must be an object/,
  );
});

test("unit: govProtected / isProtectedDomain boundaries", () => {
  assert.equal(govProtected("irs.gov"), true);
  assert.equal(govProtected("irs.gov.attacker.com"), false);
  assert.equal(govProtected("gov.uk"), false);
  assert.equal(isProtectedDomain("chase.com"), true);
  assert.equal(isProtectedDomain("sub.chase.com"), true);
  assert.equal(isProtectedDomain("purchase.com"), false);
  assert.equal(isProtectedDomain(""), false);
});
