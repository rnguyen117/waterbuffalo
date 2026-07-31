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

export const path = "/industries/electrical-contractor-marketing.html";
export const title = "Electrical Contractor Marketing | Water Buffalo Media";
export const description =
  "Electrical contractor marketing built around local demand, covering panel upgrades, EV charger installation, and local SEO for electricians.";

const trail = [
  { label: "Home", href: "../index.html" },
  { label: "Industries", href: "../industries.html" },
  { label: "Electrical" },
];

const faqItems = [
  {
    q: "What is electrician SEO?",
    a: "Electrician SEO is the process of improving how an electrical contractor appears in Google Search, Google Maps, and AI-generated answers for the services and service areas it covers, combining technical SEO, local SEO, and clear service content.",
  },
  {
    q: "Should EV charger installation have its own page?",
    a: "Yes, in most cases. EV charger installation is searched differently than general electrical repair work, and a dedicated page allows you to address the specific questions customers have about this growing service.",
  },
  {
    q: "How important is Google Business Profile for electrical contractors?",
    a: "Very important, particularly for emergency and residential searches. An accurate, well-optimized profile supports visibility in Google Maps and reinforces trust for customers comparing local electricians.",
  },
  {
    q: "Does Water Buffalo Media provide electrical safety guidance?",
    a: "No. We focus on search visibility and marketing, not electrical work itself. Any safety information, licensing claims, or technical guidance on your website must come from your business and reflect your actual credentials.",
  },
  {
    q: "Can electrical contractors benefit from separate residential and commercial pages?",
    a: "Yes. Residential and commercial electrical work involve different services, terminology, and customer priorities, and separating this content typically produces clearer results for both audiences.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Electrical Contractor Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "ELECTRICAL CONTRACTOR MARKETING",
  headline: "Electrical Contractor Marketing Built Around Local Demand.",
  body: "Electrical searches range from urgent repairs to planned upgrades like panel replacements and EV charger installation. We build visibility strategies around clear service structure and strong local presence.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo.html",
  primaryHref: "../contact.html",
  showLogoMark: true,
  logoMarkBase: "../",
})}

${renderSectionStack([
  {
    headline: "Emergency Repairs and Planned Electrical Work.",
    paragraphs: [
      "Some electrical searches are urgent, such as a customer dealing with flickering lights, a tripped panel, or an outage. Others are planned, such as a homeowner researching panel upgrades, rewiring, or EV charger installation well in advance. Each type of search benefits from different content and structure.",
      "A clear separation between emergency service pages and planned project pages helps both search engines and customers find the right information quickly.",
    ],
  },
  {
    headline: "Where We Focus for Electrical Contractors",
    paragraphs: ["Visibility strategies for electrical contractors typically emphasize:"],
    tags: [
      "Local SEO and service-area visibility",
      "Google Business Profile optimization",
      "Emergency electrical service pages",
      "Licensing and trust signals",
      "Residential and commercial separation",
      "Technical SEO",
      "AI search visibility for electrical questions",
    ],
  },
  {
    headline: "Service Opportunities",
    paragraphs: ["Electrical search demand covers a range of services worth building dedicated content around:"],
    tags: [
      "Electrical repairs",
      "Panel upgrades",
      "Wiring and rewiring",
      "EV charger installation",
      "Generator installation",
      "Lighting installation",
      "Residential electrical work",
      "Commercial electrical work",
      "Emergency electrical service",
    ],
  },
  {
    headline: "What an Electrical Contractor Strategy May Include",
    paragraphs: [
      "Depending on your current site, a strategy may include building clearer service pages, strengthening your Google Business Profile, improving technical SEO, and developing content around growing services like EV charger installation. We present licensing information as a trust signal without implying credentials that have not been verified by your business.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Electrical work requires a high level of trust, and search visibility should reflect that. We build a structure that clearly presents your services, licensing, and service areas, helping customers find and choose your business with confidence across Google Search, Google Maps, and AI-generated answers.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "HVAC Marketing", href: "hvac-marketing.html" },
  { label: "Kitchen Remodeling Marketing", href: "kitchen-remodeling-marketing.html" },
  { label: "Bathroom Remodeling Marketing", href: "bathroom-remodeling-marketing.html" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Electrical Contractor Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact.html",
})}
`;
