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

export const path = "/industries/landscaping-marketing.html";
export const title = "Landscaping Marketing and SEO | Water Buffalo Media";
export const description =
  "Landscaping marketing that supports seasonal and long-term growth, covering design, installation, lawn care, hardscaping, and local SEO for landscaping companies.";

const trail = [
  { label: "Home", href: "../" },
  { label: "Industries", href: "../industries" },
  { label: "Landscaping" },
];

const faqItems = [
  {
    q: "How does seasonality affect landscaping marketing?",
    a: "Search demand for services like lawn care, planting, and cleanup tends to rise sharply in spring and fall, while design and hardscaping projects are often researched year-round. A strategy needs to account for both seasonal spikes and steady, longer-term project searches.",
  },
  {
    q: "Should recurring services and one-time projects be marketed differently?",
    a: "Yes. Recurring lawn care customers and one-time hardscaping or design clients search differently and have different priorities, so separate content and calls to action typically perform better than a single combined page.",
  },
  {
    q: "Do landscaping companies need commercial-specific pages?",
    a: "If you serve commercial clients, a dedicated commercial maintenance page can help, since property managers and business owners often search with different terms and priorities than residential customers.",
  },
  {
    q: "How important are project photos for landscaping SEO?",
    a: "Very important. Landscaping is a visual service, and well-organized photos of design and installation work support both the buying decision and page relevance when properly structured.",
  },
  {
    q: "Can Google Maps visibility help landscaping companies win more local jobs?",
    a: "Yes. Many landscaping searches, especially for lawn care and smaller projects, have strong local intent, making Google Business Profile optimization and review management central to visibility.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Landscaping Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "LANDSCAPING MARKETING",
  headline: "Landscaping Marketing That Supports Seasonal and Long-Term Growth.",
  body: "Landscaping demand includes both recurring maintenance and larger seasonal projects. We build visibility strategies that hold up across the full calendar, not just the busiest months.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo",
  primaryHref: "../contact",
  showLogoMark: true,
  logoMarkBase: "../",
})}

${renderSectionStack([
  {
    headline: "Recurring Maintenance and Project-Based Demand.",
    paragraphs: [
      "Landscaping businesses often serve two different kinds of customers: those looking for ongoing lawn care or maintenance, and those planning a larger design, installation, or hardscaping project. These customers search differently, on different timelines, and respond to different content.",
      "A strategy that treats both audiences the same way tends to underperform for one or the other. Clear separation gives each customer type a more direct path to the right information.",
    ],
  },
  {
    headline: "Where We Focus for Landscaping Companies",
    paragraphs: ["Visibility strategies for landscaping businesses typically emphasize:"],
    tags: [
      "Local SEO and service-area pages",
      "Google Business Profile optimization",
      "Seasonal content planning",
      "Recurring versus project-based service pages",
      "Residential and commercial separation",
      "Review strategy",
      "Project galleries",
      "AI search visibility for landscaping questions",
    ],
  },
  {
    headline: "Service and Seasonal Opportunities",
    paragraphs: ["Landscaping search demand covers a wide range of services and seasonal patterns, including:"],
    tags: [
      "Landscape design",
      "Landscape installation",
      "Lawn care",
      "Hardscaping",
      "Patios",
      "Retaining walls",
      "Drainage solutions",
      "Outdoor living spaces",
      "Commercial property maintenance",
      "Spring cleanup",
      "Fall cleanup",
    ],
  },
  {
    headline: "What a Landscaping Strategy May Include",
    paragraphs: [
      "Depending on your current site, a strategy may include building distinct pages for maintenance and project-based services, strengthening your Google Business Profile ahead of peak seasons, developing project galleries, and planning content around seasonal search patterns throughout the year.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Landscaping visibility needs to work in every season, not just the busiest ones. We build a structure that supports recurring maintenance demand, larger project searches, and steady visibility across Google Search, Google Maps, and AI-generated answers throughout the year.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "Pest Control Marketing", href: "pest-control-marketing" },
  { label: "Painting Contractor Marketing", href: "painting-contractor-marketing" },
  { label: "Roofing and Siding Marketing", href: "roofing-siding-marketing" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Landscaping Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact",
})}
`;
