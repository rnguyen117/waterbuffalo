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

export const path = "/google-business-profile.html";
export const title = "Google Business Profile Optimization | Water Buffalo Media";
export const description =
  "Improve local visibility, calls, website visits, and customer trust with structured Google Business Profile optimization and ongoing local search strategy.";

const trail = [
  { label: "Home", href: "index.html" },
  { label: "Services", href: "services.html" },
  { label: "Google Business Profile" },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Google Business Profile Optimization", description, path }),
  breadcrumbSchema(trail),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "GOOGLE BUSINESS PROFILE OPTIMIZATION",
  headline: "Strengthen Your Most Visible Local Asset.",
  body: "For many customers, your Google Business Profile is the first place they see your company. We make sure it clearly communicates what you do, where you operate, and why customers should choose you.",
  compact: true,
})}

${renderSectionStack([
  {
    headline: "A Business Profile Is More Than a Listing.",
    paragraphs: [
      "Your profile influences map visibility, customer trust, phone calls, direction requests, website visits, reviews, and first impressions.",
      "It should be managed as an active search asset, not completed once and forgotten.",
    ],
  },
  {
    headline: "What We Optimize",
    tags: [
      "Primary and secondary categories",
      "Business description",
      "Services",
      "Products",
      "Service areas",
      "Hours",
      "Photos",
      "Attributes",
      "Questions and answers",
      "Review strategy",
      "Review responses",
      "Google Posts",
      "Website links",
      "UTM tracking",
      "Duplicate listing issues",
      "Suspension risk review",
      "Competitor comparison",
    ],
  },
  {
    headline: "Consistency Builds Trust.",
    paragraphs: [
      "Your profile, website, citations, services, locations, and business details should reinforce one another. Contradictory or incomplete information weakens both customer confidence and search visibility.",
    ],
  },
  {
    headline: "Built Around Meaningful Actions",
    paragraphs: ["We focus on the actions that matter:"],
    list: [
      "Qualified phone calls",
      "Website visits",
      "Direction requests",
      "Appointment requests",
      "Local discovery",
      "Customer engagement",
    ],
    listColumns: 2,
  },
])}

${renderRelatedLinks("Related Services", [
  { label: "Local SEO", href: "local-seo.html" },
  { label: "Technical SEO", href: "technical-seo.html" },
  { label: "Contact", href: "contact.html" },
])}

${renderCta({
  headline: "Turn Local Visibility Into Customer Action.",
})}
`;
