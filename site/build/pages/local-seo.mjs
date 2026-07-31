import {
  renderHero,
  renderBreadcrumbs,
  renderSectionStack,
  renderRelatedLinks,
  renderCta,
  organizationSchema,
  serviceSchema,
  breadcrumbSchema,
} from "../components.mjs";

export const path = "/local-seo.html";
export const title = "Local SEO Services | Water Buffalo Media";
export const description =
  "Build durable local visibility across Google Search and Google Maps with service-area strategy, location architecture, GBP optimization, citations, reviews, and local authority.";

const trail = [
  { label: "Home", href: "index.html" },
  { label: "Services", href: "services.html" },
  { label: "Local SEO" },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({
    name: "Local SEO",
    description,
    path,
  }),
  breadcrumbSchema(trail),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "LOCAL SEO",
  headline: "Own Your Service Area.",
  body: "Local visibility is built by proving that your business is relevant, established, and trusted in the communities you serve. We connect your website, Google Business Profile, location signals, reviews, citations, and content into one local search system.",
  compact: true,
})}

${renderSectionStack([
  {
    headline: "Every Market Has Its Own Search Ecosystem.",
    paragraphs: [
      "A business can rank well in one city and remain nearly invisible in the next. Local search depends on proximity, relevance, prominence, service relationships, location signals, and the quality of your overall digital presence.",
      "We build strategies around the real geography of your business instead of producing interchangeable city pages.",
    ],
  },
  {
    headline: "What We Strengthen",
    list: [
      "Service-area architecture",
      "City and location page strategy",
      "Google Business Profile optimization",
      "Local keyword and intent research",
      "Local landing page optimization",
      "Citation consistency",
      "Review strategy",
      "Local schema",
      "Internal linking",
      "Local content planning",
      "Competitor mapping",
      "Multi-location organization",
      "Local authority development",
      "Conversion tracking",
    ],
  },
  {
    headline: "Location Pages Should Prove Relevance.",
    paragraphs: [
      "A location page should do more than repeat a city name. It should demonstrate how your business serves that market, which services are available, what local customers need, and why your company belongs in that search result.",
      "We build location content around genuine market relevance, not duplicated templates.",
    ],
  },
  {
    headline: "Built for Businesses That Depend on Local Demand",
    list: [
      "Home improvement companies",
      "Contractors",
      "Medical practices",
      "Dental practices",
      "Law firms",
      "Automotive businesses",
      "Restaurants",
      "Local retailers",
      "Property services",
      "Multi-location companies",
    ],
    listColumns: 2,
  },
])}

${renderRelatedLinks("Related Services", [
  { label: "Google Business Profile Optimization", href: "google-business-profile.html" },
  { label: "Technical SEO", href: "technical-seo.html" },
  { label: "Contact", href: "contact.html" },
])}

${renderCta({
  headline: "Become Easier to Find Where You Actually Work.",
})}
`;
