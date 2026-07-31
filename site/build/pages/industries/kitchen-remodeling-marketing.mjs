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

export const path = "/industries/kitchen-remodeling-marketing.html";
export const title = "Kitchen Remodeling Marketing and SEO | Water Buffalo Media";
export const description =
  "Kitchen remodeling marketing for high-value projects, covering cabinet replacement, countertops, design-build services, and SEO for kitchen remodeling companies.";

const trail = [
  { label: "Home", href: "../" },
  { label: "Industries", href: "../industries" },
  { label: "Kitchen Remodeling" },
];

const faqItems = [
  {
    q: "How long do kitchen remodeling customers research before reaching out?",
    a: "Kitchen remodeling is typically one of the larger investments a homeowner makes, and research often spans weeks or months. A website needs to support that extended decision process with clear information, not just a single call to action.",
  },
  {
    q: "Do we need separate pages for cabinets, countertops, and full renovations?",
    a: "In most cases, yes. Customers researching cabinet refacing search differently than customers planning a full kitchen renovation, and separate pages let you address each audience directly.",
  },
  {
    q: "How important are project galleries for kitchen remodeling SEO?",
    a: "Very important. Kitchen remodeling is a highly visual decision, and organized project galleries support both the buying decision and, when properly structured, page relevance and search visibility.",
  },
  {
    q: "Should we include budget or pricing information?",
    a: "General budget ranges or starting points can help set expectations and reduce unqualified inquiries, as long as the information is accurate and reflects your actual pricing approach.",
  },
  {
    q: "Can design-build services be highlighted for SEO purposes?",
    a: "Yes. If design-build is part of your offering, a dedicated page explaining the process can help differentiate your business from contractors who only handle construction.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Kitchen Remodeling Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "KITCHEN REMODELING MARKETING",
  headline: "Kitchen Remodeling Marketing for High-Value Projects.",
  body: "Kitchen remodeling is a considered, high-value decision. We build visibility strategies around the visual proof, service-specific content, and local authority that support a longer customer research process.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo",
  primaryHref: "../contact",
  showLogoMark: true,
  logoMarkBase: "../",
})}

${renderSectionStack([
  {
    headline: "A High-Investment, High-Research Decision.",
    paragraphs: [
      "Kitchen remodeling projects often represent a significant investment, and customers typically research extensively before committing. They compare design styles, materials, layouts, and companies, often gathering multiple quotes before making a decision.",
      "Search visibility needs to support this entire process, from early inspiration searches through final consultation requests.",
    ],
  },
  {
    headline: "Where We Focus for Kitchen Remodeling Companies",
    paragraphs: ["Visibility strategies for kitchen remodelers typically emphasize:"],
    tags: [
      "Service-specific landing pages",
      "Project galleries and visual proof",
      "Local SEO and service-area competition",
      "Google Business Profile optimization",
      "Review strategy",
      "Consultation and budget content",
      "Technical SEO",
      "AI search visibility for remodeling questions",
    ],
  },
  {
    headline: "Service and Content Opportunities",
    paragraphs: ["Kitchen remodeling covers a range of distinct services worth building dedicated content around:"],
    tags: [
      "Full kitchen renovation",
      "Cabinet replacement",
      "Cabinet refacing",
      "Countertop installation",
      "Kitchen flooring",
      "Lighting design",
      "Layout and design changes",
      "Design-build services",
      "Consultation requests",
      "Project galleries",
    ],
  },
  {
    headline: "What a Kitchen Remodeling Strategy May Include",
    paragraphs: [
      "Depending on your current website, a strategy may include building out service-specific pages, organizing project photography, strengthening local SEO and Google Business Profile signals, and developing content that supports the longer research and consultation process. Budget or pricing information is only included when it reflects your actual approach.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Kitchen remodeling customers are making a major decision, and search visibility should reflect that. We build a structure that presents your work clearly, supports local competition, and gives customers the confidence to request a consultation.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "Bathroom Remodeling Marketing", href: "bathroom-remodeling-marketing" },
  { label: "Plumbing Marketing", href: "plumbing-marketing" },
  { label: "Electrical Contractor Marketing", href: "electrical-contractor-marketing" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Kitchen Remodeling Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact",
})}
`;
