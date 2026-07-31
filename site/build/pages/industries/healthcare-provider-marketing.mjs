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

export const path = "/industries/healthcare-provider-marketing.html";
export const title = "Healthcare Provider Marketing and SEO | Water Buffalo Media";
export const description =
  "Search visibility for medical and dental practices, combining local Google Maps presence with credible, patient-focused content.";

const trail = [
  { label: "Home", href: "../index.html" },
  { label: "Industries", href: "../industries.html" },
  { label: "Healthcare Providers" },
];

const faqItems = [
  {
    q: "How is healthcare provider SEO different from other local services?",
    a: "Patients researching a provider often weigh insurance acceptance, appointment availability, and provider credentials alongside location, so content needs to answer practical questions clearly rather than relying on location alone.",
  },
  {
    q: "How important is Google Business Profile for medical and dental practices?",
    a: "Very important for practices with physical locations. Accurate hours, insurance information, and review management all support local visibility and patient trust in Google Maps results.",
  },
  {
    q: "Does Water Buffalo Media provide medical content or advice?",
    a: "No. We focus on search visibility and content structure, not medical guidance. Any descriptions of conditions, treatments, or outcomes must be written or reviewed by qualified professionals within your practice and must not be treated as medical advice.",
  },
  {
    q: "Can multi-location healthcare practices benefit from this approach?",
    a: "Yes. Practices with multiple locations typically benefit from individual location pages and Google Business Profiles for each site, supported by consistent provider and service information across the practice.",
  },
  {
    q: "How does patient privacy factor into healthcare marketing?",
    a: "Marketing content should never reference identifiable patient information. We build general service and provider content rather than case-specific material, and any patient-related claims must be reviewed for compliance by your practice.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Healthcare Provider Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "HEALTHCARE PROVIDER MARKETING",
  headline: "Search Visibility Built on Patient Trust.",
  body: "Patients research providers, insurance, and availability before booking an appointment. We build visibility strategies around clear, credible service information and strong local presence, without ever providing medical guidance ourselves.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo.html",
  primaryHref: "../contact.html",
})}

${renderSectionStack([
  {
    headline: "Patients Research Practically, Not Just Medically.",
    paragraphs: [
      "Alongside questions about a condition or service, patients commonly search for practical details: whether a provider accepts their insurance, how soon they can be seen, and where the practice is located. Websites that answer these questions clearly tend to convert research into booked appointments more effectively than pages focused only on clinical descriptions.",
      "For practices with multiple locations, this local clarity needs to be repeated consistently across every site.",
    ],
  },
  {
    headline: "Where We Focus for Healthcare Providers",
    paragraphs: ["Visibility strategies for healthcare practices typically emphasize:"],
    tags: [
      "Local SEO for each practice location",
      "Google Business Profile optimization",
      "Provider and service page structure",
      "Review strategy",
      "Technical SEO",
      "Entity clarity for providers and specialties",
      "AI search visibility for care-related questions",
    ],
  },
  {
    headline: "Service and Content Opportunities",
    paragraphs: ["Healthcare search demand covers a range of practical and service-related topics, including:"],
    tags: [
      "New patient information",
      "Insurance and billing questions",
      "Appointment scheduling",
      "Provider bios and credentials",
      "Service and specialty pages",
      "Multi-location practice pages",
      "Telehealth availability, where offered",
    ],
  },
  {
    headline: "What a Healthcare Provider Strategy May Include",
    paragraphs: [
      "Depending on your current site, a strategy may include building clearer service and location pages, strengthening Google Business Profiles across every site, improving technical SEO, and organizing provider information for both patients and search engines. All clinical content is written to avoid medical advice and is reviewed against your practice's own guidance.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Healthcare visibility depends on clarity and trust. We build a structure that helps patients find your practice, understand what to expect, and take the next step, while keeping every claim grounded in what your practice can responsibly stand behind.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "Financial Services Marketing", href: "financial-services-marketing.html" },
  { label: "Legal Services Marketing", href: "legal-services-marketing.html" },
  { label: "SaaS and Technology Marketing", href: "saas-technology-marketing.html" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Practice's Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact.html",
})}
`;
