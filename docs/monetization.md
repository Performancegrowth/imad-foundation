# Monetization — Imad (عِماد)

> Audience: product + engineering. Defines the pricing model, entitlement
> enforcement, and the payment integration path (Sprint 14).

## 1. Plans

| Plan | Price | Projects | Analysis | BOQ & Reports | 3D export | Watermark |
|------|-------|----------|----------|---------------|-----------|-----------|
| **Free** | $0 | 1 | — | — | — | yes |
| **Pay-Per-Project** | $99 one-off | 1 full project | ✓ | ✓ | ✓ | no |
| **Office** | $299 / mo | unlimited | ✓ | ✓ | ✓ | no |
| **Enterprise** | $999 / mo | unlimited + API | ✓ | ✓ | ✓ | no |

Annual billing gives **2 months free** (~17 % discount) on Office and
Enterprise. Value framing: one avoided re-design cycle or one hour of senior
engineer time exceeds the monthly Office fee — the pricing page leads with
"pays for itself on the first project".

## 2. Entitlement Matrix (server-enforced)

`app/services/subscriptions.py` is the single source of truth:

```python
PLANS = {
  "free":        Entitlements(max_projects=1, analysis=False, exports=False, watermark=True),
  "per_project": Entitlements(max_projects=1, analysis=True,  exports=True,  watermark=False),
  "office":      Entitlements(max_projects=None, ...),
  "enterprise":  Entitlements(..., api_access=True),
}
```

Enforcement points:

* `POST /api/v1/analyze` and `/api/v1/generate-designs` → 402 when
  `analysis=False`, message links to the pricing page.
* BOQ/carbon PDF & Excel export → 402 when `exports=False`.
* 3D glTF export renders a watermark bar when `watermark=True`.
* `GET /api/v1/analytics` (business analytics) → `enterprise` only.
* Free-tier project creation beyond `max_projects` → 402 with upgrade hint.

The frontend mirrors these states for UX (locked buttons with tooltips) but
**the API is the enforcement boundary**.

## 3. Checkout & Webhooks (Stripe placeholder)

```
POST /api/v1/subscriptions/upgrade   → returns {checkout_url} (Stripe stub)
POST /api/v1/payments/webhook        → receives Stripe events (stub)
```

Go-live checklist:

1. Replace `subscriptions.py::create_checkout_session` stub with a real
   Stripe Checkout Session (prices defined in Stripe dashboard, not code).
2. Verify webhook signatures (`stripe.Webhook.construct_event`) before
   trusting payloads — **currently unverified by design**.
3. Handle `checkout.session.completed`, `invoice.paid`,
   `customer.subscription.deleted` → flip the local `Subscription` record.
4. Store `stripe_customer_id` on the subscription record for portal links.
5. Tax/VAT: delegate to Stripe Tax.

## 4. API Access (Enterprise add-on)

* `POST /api/v1/api-keys/generate` issues scoped keys (`read`, `analyze`,
  `export`); only Enterprise entitlements may create them.
* Metering: each key call increments a per-key counter (analytics endpoint
  reports usage). Overage pricing: $0.004 per analysis call above 1,000/mo
  (placeholder — tune with real cost data).

## 5. White-Label (Enterprise)

`WhiteLabelSettings` (`/api/v1/whitelabel`) lets Enterprise tenants brand the
workspace: org name, logo URL, primary/accent colors, custom domain. The
frontend reads these from `/api/v1/whitelabel` at boot and overrides the CSS
custom properties (`--brand`, `--accent`) — no rebuild required.

## 6. Revenue Analytics

`GET /api/v1/analytics` aggregates: MRR by plan, conversion rate
(free→paid), churn, API call volume, and per-feature activation (analysis,
BOQ, 3D). The Admin dashboard renders these with the shared chart kit.

## 7. Packaging Rules of Thumb

* Never gate **correctness or safety** features — compliance checks and
  validation runs stay free to build trust (they are the moat).
* Gate **throughput and output artifacts** (exports, API, white-label) —
  what firms pay for is paperwork and integration, not math.
