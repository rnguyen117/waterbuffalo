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

export const path = "/industries/hvac-marketing.html";
export const title = "HVAC Marketing and SEO Services | Water Buffalo Media";
export const description =
  "HVAC marketing built for year-round search visibility, covering seasonal demand, emergency repair searches, Google Maps, and local SEO for HVAC companies.";

const trail = [
  { label: "Home", href: "../" },
  { label: "Industries", href: "../industries" },
  { label: "HVAC" },
];

const faqItems = [
  {
    q: "What is HVAC SEO?",
    a: "HVAC SEO is the process of improving how an HVAC company appears in Google Search, Google Maps, and AI-generated answers for the services it offers and the areas it serves. It includes technical SEO, local SEO, Google Business Profile optimization, and content built around real heating and cooling services.",
  },
  {
    q: "How long does HVAC SEO take?",
    a: "Timelines vary based on the current state of a website, the competitiveness of the service area, and how much content and technical work is needed. Search visibility tends to build steadily over months rather than appearing overnight, and we do not promise a fixed timeline or guaranteed ranking position.",
  },
  {
    q: "Can SEO help an HVAC company appear in Google Maps?",
    a: "Google Business Profile optimization, citation consistency, and review strategy are central to local map visibility. We treat your profile as an active search asset, not a one-time listing, since map rankings respond to ongoing signals rather than a single setup step.",
  },
  {
    q: "Should HVAC companies create separate pages for each service?",
    a: "In most cases, yes. Furnace repair, air-conditioning replacement, heat pump installation, and maintenance plans are searched differently and serve different customer needs. Distinct, well-structured service pages give search engines and customers a clearer picture than a single page trying to cover everything.",
  },
  {
    q: "How does seasonality affect HVAC marketing?",
    a: "Heating and cooling demand shifts throughout the year, and search volume for repair, replacement, and maintenance content shifts with it. A durable strategy accounts for both sides of the season instead of only optimizing for whichever service is in demand right now.",
  },
  {
    q: "Can HVAC content appear in AI-generated answers?",
    a: "AI platforms draw on clear, well-structured, and credible content when summarizing services and recommending businesses. Entity clarity, structured data, and consistent service information all support that visibility, though no strategy can guarantee inclusion in a specific AI-generated response.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "HVAC Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "HVAC MARKETING",
  headline: "HVAC Marketing Built for Year-Round Search Visibility.",
  body: "Heating and cooling demand shifts with the seasons, but search visibility has to hold up all year. We build HVAC marketing strategies around emergency repair searches, seasonal maintenance, and the local trust signals that turn searches into service calls.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo",
  primaryHref: "../contact",
  showLogoMark: true,
  logoMarkBase: "../",
})}

${renderSectionStack([
  {
    headline: "How HVAC Customers Actually Search.",
    paragraphs: [
      "HVAC searches split into two very different categories. A homeowner with no heat on a cold night searches with urgency and expects an immediate answer, usually starting with Google Maps or a quick search for '24 hour HVAC repair near me.' A homeowner researching a full system replacement searches slowly, comparing efficiency ratings, financing, and installer reputation over days or weeks.",
      "A single generic homepage struggles to serve both. Strong HVAC visibility requires content and structure built around each type of search, not one page trying to answer every question at once.",
    ],
  },
  {
    headline: "Where We Focus for HVAC Companies",
    paragraphs: [
      "Every HVAC business is different, but visibility strategies for this industry typically emphasize:",
    ],
    tags: [
      "Local SEO and service-area structure",
      "Google Business Profile optimization",
      "Emergency and same-day service pages",
      "Seasonal maintenance content",
      "Residential and commercial service separation",
      "Review strategy and response management",
      "Technical SEO and site speed",
      "AI search visibility for service-related questions",
    ],
  },
  {
    headline: "Service and Seasonal Opportunities",
    paragraphs: [
      "HVAC search demand includes a wide range of specific services and recurring seasonal patterns worth building content around:",
    ],
    tags: [
      "Furnace repair",
      "Furnace installation",
      "Air-conditioning repair",
      "Air-conditioning replacement",
      "Heat pump installation",
      "Indoor air quality",
      "Maintenance plans",
      "Financing options",
      "Emergency repair",
      "Spring AC tune-ups",
      "Fall furnace inspections",
      "Residential HVAC",
      "Commercial HVAC",
    ],
  },
  {
    headline: "What an HVAC Search Strategy May Include",
    paragraphs: [
      "Depending on your current website and market, a strategy may include improving technical SEO fundamentals, building or restructuring service and location pages, strengthening your Google Business Profile, developing seasonal content, and improving how clearly your services are described for both search engines and AI-generated answers. We prioritize the changes most likely to affect visibility and calls, rather than producing generic activity without a clear reason.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "We approach HVAC visibility as a full search ecosystem: your website, your Google Business Profile, your reviews, and the way AI platforms describe your business all reinforce one another. Rather than treating SEO as a list of disconnected tasks, we build a structure that supports steady, durable visibility across heating season, cooling season, and everything in between.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "Plumbing Marketing", href: "plumbing-marketing" },
  { label: "Electrical Contractor Marketing", href: "electrical-contractor-marketing" },
  { label: "Roofing and Siding Marketing", href: "roofing-siding-marketing" },
])}

${renderCta({
  headline: "Ready to Strengthen Your HVAC Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact",
})}
`;
