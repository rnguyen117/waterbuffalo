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

export const path = "/global-seo.html";
export const title = "Global and International SEO Services | Water Buffalo Media";
export const description =
  "Expand into international search markets with language targeting, hreflang, localized content, global site architecture, and technical SEO.";

const trail = [
  { label: "Home", href: "index.html" },
  { label: "Services", href: "services.html" },
  { label: "Global SEO" },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Global SEO", description, path, areaServed: "Worldwide" }),
  breadcrumbSchema(trail),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "GLOBAL SEO",
  headline: "Expand Without Losing Clarity.",
  body: "International search visibility requires more than translating existing pages. Each market has its own language, search behavior, competition, cultural expectations, and technical requirements.",
  compact: true,
})}

${renderSectionStack([
  {
    headline: "Global Reach Requires Local Understanding.",
    paragraphs: [
      "A strategy that works in one country may not translate directly into another. Search language, product terminology, purchasing behavior, regulations, and user expectations can change from market to market.",
      "We create a clear framework for expansion while protecting the strength of your primary website.",
    ],
  },
  {
    headline: "What We Address",
    list: [
      "International keyword research",
      "Market opportunity analysis",
      "Country and language targeting",
      "Hreflang implementation",
      "International URL structure",
      "Localized content planning",
      "Translation quality guidance",
      "International technical audits",
      "Duplicate content prevention",
      "Regional search intent",
      "Global internal linking",
      "Search performance monitoring",
    ],
  },
  {
    headline: "Translation Is Not Localization.",
    paragraphs: [
      "Literal translation often misses the way customers actually search. We structure international content around local terminology, search behavior, customer expectations, and market-specific intent.",
    ],
  },
  {
    headline: "One Brand, Clearly Understood Across Markets",
    paragraphs: [
      "Our goal is to preserve a consistent brand while giving search engines and customers the correct experience for each location and language.",
    ],
  },
])}

${renderRelatedLinks("Related Services", [
  { label: "Technical SEO", href: "technical-seo.html" },
  { label: "National SEO", href: "national-seo.html" },
  { label: "Generative Engine Optimization", href: "ai-search.html" },
])}

${renderCta({
  headline: "Create a Stronger Foundation for International Growth.",
})}
`;
