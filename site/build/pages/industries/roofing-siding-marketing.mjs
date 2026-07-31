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

export const path = "/industries/roofing-siding-marketing.html";
export const title = "Roofing and Siding Marketing and SEO | Water Buffalo Media";
export const description =
  "Roofing and siding marketing built for competitive local markets, covering repair, replacement, storm-driven searches, and local SEO for roofing contractors.";

const trail = [
  { label: "Home", href: "../index.html" },
  { label: "Industries", href: "../industries.html" },
  { label: "Roofing & Siding" },
];

const faqItems = [
  {
    q: "How is roofing SEO different from other home services?",
    a: "Roofing search demand can spike suddenly after storms, alongside a steadier stream of planned repair and replacement searches. A strategy needs to account for both the sudden surges and the ongoing baseline demand, rather than optimizing for only one pattern.",
  },
  {
    q: "Does Water Buffalo Media help with insurance claims or storm damage content?",
    a: "We can help present information about storm damage services and the general process of working with insurance, but we do not provide legal or insurance advice, and we do not make promises about claim approval or coverage outcomes. Any specific insurance guidance should come from your team or a qualified professional.",
  },
  {
    q: "Should roofing and siding be treated as one service or separate pages?",
    a: "In most cases, roofing and siding should have distinct pages, since customers search for them separately and each involves different materials, processes, and considerations. A combined overview page can still exist, but dedicated pages give each service room to be explained clearly.",
  },
  {
    q: "How important are project galleries for roofing companies?",
    a: "Photos of completed roofing and siding projects support customer trust and can reinforce local relevance when organized with proper context and location information.",
  },
  {
    q: "Can SEO help with commercial roofing visibility as well as residential?",
    a: "Yes, though residential and commercial roofing searches differ in terminology and customer priorities. Separating this content, rather than combining it into one general page, typically produces clearer results for both audiences.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Roofing and Siding Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "ROOFING AND SIDING MARKETING",
  headline: "Roofing and Siding Marketing Built for Competitive Local Markets.",
  body: "Roofing and siding demand ranges from urgent storm-driven repairs to planned replacement projects. We build visibility strategies that hold up across both, with clear service structure and strong local presence.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo.html",
  primaryHref: "../contact.html",
})}

${renderSectionStack([
  {
    headline: "Two Different Kinds of Roofing Demand.",
    paragraphs: [
      "Roofing and siding searches tend to fall into two categories: sudden, urgent searches following storm damage or a visible leak, and slower, planned searches for a full roof or siding replacement. Emergency searches reward fast, clear local visibility, while planned replacement searches reward detailed service information, materials comparisons, and project galleries.",
      "A single generic homepage rarely serves both search types well. Building distinct paths for emergency and planned searches strengthens visibility for each.",
    ],
  },
  {
    headline: "Where We Focus for Roofing and Siding Companies",
    paragraphs: ["Visibility strategies for roofing and siding businesses typically emphasize:"],
    tags: [
      "Local SEO and service-area competition",
      "Emergency and storm-damage service pages",
      "Google Business Profile optimization",
      "Review strategy and local trust",
      "Residential and commercial separation",
      "Project galleries",
      "Technical SEO",
      "AI search visibility for roofing questions",
    ],
  },
  {
    headline: "Service and Material Opportunities",
    paragraphs: ["Roofing and siding search demand spans a range of services and materials, including:"],
    tags: [
      "Roof repair",
      "Roof replacement",
      "Storm damage assessment",
      "Emergency roof repair",
      "Asphalt shingle roofing",
      "Metal roofing",
      "Siding installation",
      "Siding replacement",
      "Roof inspections",
      "Residential roofing",
      "Commercial roofing",
    ],
  },
  {
    headline: "What a Roofing and Siding Strategy May Include",
    paragraphs: [
      "Depending on your current site, a strategy may include building distinct pages for emergency and planned services, strengthening your Google Business Profile across every service area, developing project galleries, and improving technical SEO. We present insurance-related content carefully and without offering legal or coverage advice, and we never promise storm-claim approval or guaranteed lead volume.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Roofing and siding companies operate in some of the most locally competitive search categories. We build a structure that supports both urgent and planned demand, strengthens your standing across every service area, and gives your business a clearer presence in Google Search, Google Maps, and AI-generated answers.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "Window Installation Marketing", href: "window-installation-marketing.html" },
  { label: "HVAC Marketing", href: "hvac-marketing.html" },
  { label: "Painting Contractor Marketing", href: "painting-contractor-marketing.html" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Roofing and Siding Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact.html",
})}
`;
