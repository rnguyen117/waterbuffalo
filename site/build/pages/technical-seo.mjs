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

export const path = "/technical-seo.html";
export const title = "Technical SEO Services | Water Buffalo Media";
export const description =
  "Improve crawling, indexing, site speed, Core Web Vitals, structured data, architecture, and search performance with technical SEO services.";

const trail = [
  { label: "Home", href: "./" },
  { label: "Services", href: "services" },
  { label: "Technical SEO" },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Technical SEO", description, path }),
  breadcrumbSchema(trail),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "TECHNICAL SEO",
  headline: "Build a Website Search Engines Can Read.",
  body: "Strong content cannot perform if search engines struggle to crawl, render, interpret, or index your website. We identify the structural problems limiting visibility and build a stronger technical foundation.",
  compact: true,
})}

${renderSectionStack([
  {
    headline: "Technical Problems Quietly Limit Growth.",
    paragraphs: [
      "A website may look functional while hiding serious search issues beneath the surface. Broken internal links, duplicate URLs, weak architecture, poor rendering, incorrect canonical tags, slow templates, and indexing problems can reduce the value of every page you publish.",
    ],
  },
  {
    headline: "What We Examine",
    tags: [
      "Crawlability",
      "Indexing",
      "Site architecture",
      "Core Web Vitals",
      "Page speed",
      "Mobile usability",
      "JavaScript rendering",
      "Canonical tags",
      "Redirects",
      "XML sitemaps",
      "Robots.txt",
      "Structured data",
      "Duplicate content",
      "Broken links",
      "Orphan pages",
      "URL structure",
      "Internal linking",
      "Pagination",
      "International signals",
      "Log file analysis when available",
    ],
  },
  {
    headline: "Technical SEO Should Create Clarity.",
    paragraphs: [
      "Our goal is not to produce a long list of technical errors without context. We identify which issues actually affect discovery, rankings, performance, or conversion, then prioritize them by business impact.",
    ],
  },
  {
    headline: "A Stronger Site Makes Every Other Strategy Work Better.",
    paragraphs: [
      "When the technical foundation is healthy, content is easier to discover, internal authority flows more effectively, users have a better experience, and future improvements become easier to scale.",
    ],
  },
])}

${renderRelatedLinks("Related Services", [
  { label: "Local SEO", href: "local-seo" },
  { label: "National SEO", href: "national-seo" },
  { label: "Global SEO", href: "global-seo" },
  { label: "Generative Engine Optimization", href: "ai-search" },
  { label: "Google Business Profile Optimization", href: "google-business-profile" },
])}

${renderCta({
  headline: "Remove the Technical Barriers Holding Back Your Visibility.",
})}
`;
