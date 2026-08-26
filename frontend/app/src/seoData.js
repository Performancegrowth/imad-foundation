// Shared SEO / AEO data for Imad's public pages.
// Keeps FAQ content and JSON-LD schemas in one place so page files stay small.

export const SITE_URL = 'https://imad.ai'

export const FAQS = [
  {
    q: 'Can AI design a building structure?',
    a: 'Yes. Imad uses generative AI to design structural systems — columns, beams, footings, floors and reinforcement — that meet code, then validates them with finite-element analysis.',
  },
  {
    q: 'Is Imad compliant with Saudi Building Code?',
    a: 'Imad supports SBC 304 in addition to ACI 318 and Eurocode 2, producing designs and reports aligned with Saudi construction practice.',
  },
  {
    q: 'How does Imad compare to ETABS or STAAD?',
    a: 'ETABS and STAAD are manual analysis tools. Imad is an autonomous engine: it generates the model, runs the analysis, and produces designs, bills of quantities, and sustainability reports automatically.',
  },
  {
    q: 'What does Imad cost?',
    a: 'Imad offers a free tier, Pay-Per-Project at $99, an Office plan at $299 per month, and an Enterprise plan at $999 per month for multi-team deployments.',
  },
  {
    q: 'Do I need a CAD file to use Imad?',
    a: 'No. Describe your project, import a CAD/DXF or IFC/BIM model, or use the plan wizard — Imad builds the structure for you either way.',
  },
  {
    q: 'Can Imad handle multi-story buildings?',
    a: 'Yes. Imad models multiple floors, distributes lateral and gravity loads, and checks storey drift and instability across the full building height.',
  },
  {
    q: 'What is generative design?',
    a: 'Generative design explores thousands of valid structural options in minutes and surfaces the best-performing alternatives for you to compare, refine, and select.',
  },
  {
    q: 'Does Imad provide BOQ and BBS?',
    a: "Yes. Imad produces a complete Bill of Quantities and a cutting-optimised Bar Bending Schedule (waste target below 2%), exportable to PDF and Excel.",
  },
  {
    q: 'Is my design safe?',
    a: 'Safety is a primary constraint. Every result is validated against code load combinations and limit-state factors, and reviewed before you sign.',
  },
  {
    q: 'How long does it take to get a design?',
    a: 'A typical design completes in minutes once the inputs are ready — down from days of manual labor with conventional tools.',
  },
]

export function organizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Imad',
    url: SITE_URL,
    logo: 'https://imad.ai/logo.png',
    slogan: 'The Autonomous Engineering Engine',
    description: 'AI Generative Design, Zero Clashes, Full Sustainability',
  }
}

export function softwareAppSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Imad',
    applicationCategory: 'EngineeringApplication',
    operatingSystem: 'Web',
    description: 'Autonomous AI-powered structural engineering platform for design, BOQ, and sustainability.',
    offers: [
      { '@type': 'Offer', name: 'Free', price: '0', priceCurrency: 'USD' },
      { '@type': 'Offer', name: 'Pay-Per-Project', price: '99', priceCurrency: 'USD' },
      { '@type': 'Offer', name: 'Office', price: '299', priceCurrency: 'USD' },
      { '@type': 'Offer', name: 'Enterprise', price: '999', priceCurrency: 'USD' },
    ],
    featureList: [
      'Generative AI structural design',
      'BOQ and Bar Bending Schedule generation',
      'Carbon footprint calculation',
      'Multi-story building analysis',
      'IFC/BIM import/export',
      'Compliance with ACI 318, Eurocode 2, SBC 304',
    ],
    aggregateRating: { '@type': 'AggregateRating', ratingValue: '4.8', reviewCount: '25' },
  }
}

export function faqPageSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQS.map((f) => ({
      '@type': 'Question',
      name: f.q,
      acceptedAnswer: { '@type': 'Answer', text: f.a },
    })),
  }
}