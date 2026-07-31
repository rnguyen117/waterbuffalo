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

export const path = "/national-seo.html";
export const title = "National SEO Services | Water Buffalo Media";
export const description =
  "Build scalable national search authority through content architecture, technical SEO, internal linking, topical depth, and competitive search strategy.";

const trail = [
  { label: "Home", href: "index.html" },
  { label: "Services", href: "services.html" },
  { label: "National SEO" },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "National SEO", description, path }),
  breadcrumbSchema(trail),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "NATIONAL SEO",
  headline: "Build Authority That Scales.",
  body: "National visibility requires more than targeting higher-volume keywords. It requires a website with enough depth, clarity, technical strength, and industry authority to compete across a broader market.",
  compact: true,
})}

${renderSectionStack([
  {
    headline: "National SEO Is an Authority Problem.",
    paragraphs: [
      "Competing nationally means earning trust across entire topics, services, and customer journeys. A handful of isolated pages cannot create that level of authority.",
      "We map the full search landscape around your business and create a structure that allows every page to support the next.",
    ],
  },
  {
    headline: "What We Build",
    list: [
      "National keyword strategy",
      "Search intent mapping",
      "Content architecture",
      "Topic clusters",
      "Service page development",
      "Editorial planning",
      "Internal linking systems",
      "Competitor gap analysis",
      "Technical SEO",
      "Authority development",
      "Digital PR recommendations",
      "Conversion-focused optimization",
      "Reporting tied to business outcomes",
    ],
  },
  {
    headline: "From Individual Keywords to Complete Topics",
    paragraphs: [
      "Search engines evaluate whether a website understands a subject deeply enough to deserve visibility. We help businesses cover important topics with purpose, avoid unnecessary content, and connect related pages into a clear hierarchy.",
    ],
  },
  {
    headline: "Designed for Sustainable Expansion",
    paragraphs: [
      "As your website grows, the system should become stronger rather than harder to manage. We create structures that support new products, services, markets, resources, and campaigns without weakening the rest of the site.",
    ],
  },
])}

${renderRelatedLinks("Related Services", [
  { label: "Technical SEO", href: "technical-seo.html" },
  { label: "Generative Engine Optimization", href: "ai-search.html" },
  { label: "Global SEO", href: "global-seo.html" },
])}

${renderCta({
  headline: "Build a Search Presence Strong Enough to Scale.",
})}
`;
