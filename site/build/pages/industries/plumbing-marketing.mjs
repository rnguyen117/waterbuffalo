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

export const path = "/industries/plumbing-marketing.html";
export const title = "Plumbing Marketing and SEO Services | Water Buffalo Media";
export const description =
  "Plumbing marketing for urgent and planned service searches, covering emergency plumbing, water heaters, drain cleaning, and local SEO for plumbers.";

const trail = [
  { label: "Home", href: "../index.html" },
  { label: "Industries", href: "../industries.html" },
  { label: "Plumbing" },
];

const faqItems = [
  {
    q: "What is plumbing SEO?",
    a: "Plumbing SEO covers the technical, local, and content work needed to help a plumbing company appear in Google Search, Google Maps, and AI-generated answers for both emergency and planned plumbing services in its service area.",
  },
  {
    q: "How does emergency search behavior affect plumbing marketing?",
    a: "Emergency plumbing searches, such as a burst pipe or major leak, tend to happen quickly and often start with Google Maps. Clear service-area pages, an accurate Google Business Profile, and fast-loading pages all support visibility for these high-urgency moments.",
  },
  {
    q: "Should residential and commercial plumbing be separated?",
    a: "In most cases, yes. Residential and commercial plumbing customers search with different terms and priorities, and separate pages allow each audience to find relevant, specific information.",
  },
  {
    q: "What plumbing services benefit most from dedicated pages?",
    a: "Services like water heater repair and installation, drain cleaning, sewer line work, leak detection, and repiping are commonly searched individually and typically perform better with their own dedicated pages rather than being combined into one general plumbing services page.",
  },
  {
    q: "Can SEO help plumbing companies appear in AI-generated answers?",
    a: "Clear service descriptions, structured data, and consistent business information all support how AI platforms understand and reference a plumbing business, though no strategy can guarantee inclusion in a specific AI-generated response.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Plumbing Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "PLUMBING MARKETING",
  headline: "Plumbing Marketing for Urgent and Planned Service Searches.",
  body: "Plumbing search demand ranges from immediate emergencies to planned installation projects. We build visibility strategies that serve both, with clear service structure and strong local presence.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo.html",
  primaryHref: "../contact.html",
})}

${renderSectionStack([
  {
    headline: "Immediate-Intent and Research-Driven Searches.",
    paragraphs: [
      "A customer with a burst pipe searches with urgency and expects an immediate, local answer. A customer planning a repiping project or a water heater upgrade researches more slowly, comparing options and reading about the process before reaching out.",
      "Plumbing marketing needs to account for both patterns, with clear paths for emergency contact and detailed content for planned projects.",
    ],
  },
  {
    headline: "Where We Focus for Plumbing Companies",
    paragraphs: ["Visibility strategies for plumbing businesses typically emphasize:"],
    tags: [
      "Local SEO and service-area pages",
      "Emergency plumbing visibility",
      "Google Business Profile optimization",
      "Review strategy and response management",
      "Residential and commercial separation",
      "Clear contact and conversion paths",
      "Technical SEO",
      "AI search visibility for plumbing questions",
    ],
  },
  {
    headline: "Service Opportunities",
    paragraphs: ["Plumbing search demand covers a wide range of services worth building dedicated content around:"],
    tags: [
      "Emergency plumbing",
      "Drain cleaning",
      "Water heater repair",
      "Water heater installation",
      "Sewer line repair",
      "Leak detection",
      "Repiping",
      "Fixture installation",
      "Residential plumbing",
      "Commercial plumbing",
    ],
  },
  {
    headline: "What a Plumbing Search Strategy May Include",
    paragraphs: [
      "Depending on your current site, a strategy may include building or restructuring service pages, strengthening your Google Business Profile across service areas, improving technical SEO and page speed, and developing content that clearly separates emergency and planned services. We prioritize the changes most likely to affect visibility and calls.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Plumbing customers need to find a trustworthy, local answer quickly, whether they are dealing with an emergency or planning a project. We build a search presence that connects your website, Google Business Profile, and reviews so both types of customers can find and choose your business with confidence.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "HVAC Marketing", href: "hvac-marketing.html" },
  { label: "Bathroom Remodeling Marketing", href: "bathroom-remodeling-marketing.html" },
  { label: "Kitchen Remodeling Marketing", href: "kitchen-remodeling-marketing.html" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Plumbing Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact.html",
})}
`;
