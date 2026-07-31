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

export const path = "/ai-search.html";
export const title = "Generative Engine Optimization and AI Search | Water Buffalo Media";
export const description =
  "Improve how AI platforms understand, reference, and recommend your business through entity clarity, structured content, authority signals, and AI search optimization.";

const trail = [
  { label: "Home", href: "index.html" },
  { label: "Services", href: "services.html" },
  { label: "AI Search" },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Generative Engine Optimization", description, path }),
  breadcrumbSchema(trail),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "GENERATIVE ENGINE OPTIMIZATION",
  headline: "Be Recognized by AI Search.",
  body: "AI platforms do not simply return a list of links. They interpret information, compare sources, summarize concepts, and recommend answers. Your business needs to be clear, credible, and connected enough to become part of that process.",
  compact: true,
})}

${renderSectionStack([
  {
    headline: "Search Is Becoming an Answer System.",
    paragraphs: [
      "Customers are using Google AI Overviews, ChatGPT, Gemini, Claude, Perplexity, and other platforms to research services, products, companies, and decisions.",
      "Visibility now depends on whether these systems understand who you are, what you know, what you offer, and why your information should be trusted.",
    ],
  },
  {
    headline: "What We Strengthen",
    list: [
      "Entity clarity",
      "Brand and service relationships",
      "Structured data",
      "Semantic content",
      "Source attribution",
      "Expert signals",
      "Author and company credibility",
      "FAQ and answer formatting",
      "Topical depth",
      "Brand mentions",
      "Knowledge graph consistency",
      "Crawlable content",
      "Citation-worthy resources",
      "AI visibility monitoring",
    ],
  },
  {
    headline: "GEO Does Not Replace SEO.",
    paragraphs: [
      "Generative Engine Optimization builds on strong technical SEO, useful content, clear entities, and established authority. AI systems still depend heavily on the same information ecosystem that supports traditional search.",
      "We strengthen both together.",
    ],
  },
  {
    headline: "Become Easier to Interpret, Cite, and Recommend.",
    paragraphs: [
      "The goal is not to manipulate an AI platform. The goal is to make your business a clearer and more reliable source.",
    ],
  },
])}

${renderRelatedLinks("Related Services", [
  { label: "Technical SEO", href: "technical-seo.html" },
  { label: "National SEO", href: "national-seo.html" },
  { label: "About", href: "about.html" },
])}

${renderCta({
  headline: "Prepare Your Search Presence for the Next Generation of Discovery.",
})}
`;
