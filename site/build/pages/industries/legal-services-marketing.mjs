import {
  renderHero,
  renderBreadcrumbs,
  renderSectionStack,
  renderFaq,
  renderRelatedLinks,
  renderCta,
  organizationSchema,
  serviceSchema,
  breadcrumbSchema,
  faqSchema,
} from "../../components.mjs";

export const path = "/industries/legal-services-marketing.html";
export const title = "Legal Services Marketing and SEO | Water Buffalo Media";
export const description =
  "Search visibility for law firms, combining practice-area authority, local search presence, and national reach for firms serving broader markets.";

const trail = [
  { label: "Home", href: "../index.html" },
  { label: "Industries", href: "../industries.html" },
  { label: "Legal Services" },
];

const faqItems = [
  {
    q: "How does law firm SEO differ by practice area?",
    a: "Practice areas like personal injury, family law, and estate planning are searched with different intent, urgency, and terminology. A strategy built around one practice area rarely transfers directly to another, so each typically needs its own dedicated content and structure.",
  },
  {
    q: "Should law firms prioritize local SEO or national SEO?",
    a: "It depends on how the firm operates. A single-location practice usually benefits most from strong local SEO and Google Business Profile visibility, while a firm serving multiple states or a national client base needs broader content authority and technical SEO to compete beyond one city.",
  },
  {
    q: "Does Water Buffalo Media make claims about case outcomes or results?",
    a: "No. We do not add claims about case outcomes, settlement amounts, or guaranteed results. Any such statements must come directly from your firm and comply with the advertising rules that apply in your jurisdiction.",
  },
  {
    q: "How important are reviews for legal services marketing?",
    a: "Reviews often play a meaningful role in local visibility and client trust, though firms should ensure any review collection and display practices comply with applicable bar association and advertising rules.",
  },
  {
    q: "Can legal content appear in AI-generated answers?",
    a: "Clear, well-organized content that accurately explains practice areas and processes can support how AI platforms summarize legal topics and reference firms, though no strategy can guarantee inclusion in a specific AI-generated response.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Legal Services Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "LEGAL SERVICES MARKETING",
  headline: "Search Visibility Built Around Practice Area Authority.",
  body: "Legal searches range from urgent, local searches after an incident to slower, research-driven searches for ongoing representation. We build visibility strategies around each practice area, with the local and national reach your firm actually needs.",
  secondaryLabel: "Explore National SEO",
  secondaryHref: "../national-seo.html",
  primaryHref: "../contact.html",
})}

${renderSectionStack([
  {
    headline: "Practice Areas Behave Like Separate Businesses.",
    paragraphs: [
      "A personal injury search after an accident is urgent and local. A search for estate planning guidance unfolds slowly and often starts with general research. Combining every practice area into one generic page tends to underperform for all of them.",
      "Strong legal visibility usually comes from treating each practice area as its own focused topic, with content and structure built around how clients in that situation actually search.",
    ],
  },
  {
    headline: "Where We Focus for Law Firms",
    paragraphs: ["Visibility strategies for law firms typically emphasize:"],
    tags: [
      "Practice-area content architecture",
      "Local SEO for single-location firms",
      "National SEO for multi-market firms",
      "Google Business Profile optimization",
      "Technical SEO",
      "Entity clarity and attorney credential pages",
      "AI search visibility for legal questions",
    ],
  },
  {
    headline: "Practice Area Opportunities",
    paragraphs: ["Legal search demand spans a range of practice areas worth building dedicated content around:"],
    tags: [
      "Personal injury",
      "Family law",
      "Estate planning",
      "Business and corporate law",
      "Criminal defense",
      "Employment law",
      "Immigration law",
      "Attorney and case-type consultations",
    ],
  },
  {
    headline: "What a Legal Services Strategy May Include",
    paragraphs: [
      "Depending on your current site, a strategy may include building distinct, well-structured pages for each practice area, strengthening local SEO and Google Business Profile signals, improving technical SEO, and developing content that reflects real client questions. We do not add claims about case outcomes, and any advertising-related content is written to reflect the requirements of your jurisdiction as provided by your firm.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Legal services search is highly competitive and highly trust-dependent. We build a structure that presents each practice area clearly, supports local and national visibility as appropriate, and positions your firm credibly across Google Search, Google Maps, and AI-generated answers.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "Financial Services Marketing", href: "financial-services-marketing.html" },
  { label: "Healthcare Provider Marketing", href: "healthcare-provider-marketing.html" },
  { label: "SaaS and Technology Marketing", href: "saas-technology-marketing.html" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Law Firm's Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact.html",
})}
`;
