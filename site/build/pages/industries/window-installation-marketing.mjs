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

export const path = "/industries/window-installation-marketing.html";
export const title = "Window Installation Marketing and SEO | Water Buffalo Media";
export const description =
  "Window installation marketing that reaches ready-to-buy homeowners, covering replacement windows, product comparisons, and local SEO for window installers.";

const trail = [
  { label: "Home", href: "../" },
  { label: "Industries", href: "../industries" },
  { label: "Window Installation" },
];

const faqItems = [
  {
    q: "What is window installation SEO?",
    a: "Window installation SEO covers the technical, local, and content work needed to help a window company appear in Google Search, Google Maps, and AI-generated answers for replacement, installation, and product-related searches in its service area.",
  },
  {
    q: "Should we compare window materials on our website?",
    a: "Clear, factual comparisons of window materials such as vinyl, wood, and fiberglass can help customers understand their options and support relevant content, as long as claims about performance or savings are accurate and supported by your actual products.",
  },
  {
    q: "Do window companies need pages for patio doors and entry doors too?",
    a: "If those are services you offer, dedicated pages help, though they should typically be treated as secondary to your core window replacement and installation pages rather than given equal top-level priority unless doors represent a major part of your business.",
  },
  {
    q: "How important are reviews and warranties for window installation marketing?",
    a: "Reviews, warranty information, and clear installer credentials all support trust during a purchase that customers often research carefully. Presenting this information clearly on relevant pages supports both users and search visibility.",
  },
  {
    q: "Can SEO help distinguish us from manufacturers selling directly?",
    a: "Clearly explaining your role as an installer, your service area, your process, and your warranty support can help customers understand the difference between working with a local installer and purchasing directly from a manufacturer.",
  },
];

export const schemas = [
  organizationSchema(),
  serviceSchema({ name: "Window Installation Marketing", description, path }),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "WINDOW INSTALLATION MARKETING",
  headline: "Window Installation Marketing That Reaches Ready-to-Buy Homeowners.",
  body: "Window replacement customers compare products, installers, and estimates before making a decision. We build visibility strategies around that comparison process, with clear product information and strong local presence.",
  secondaryLabel: "Explore Local SEO",
  secondaryHref: "../local-seo",
  primaryHref: "../contact",
  showLogoMark: true,
  logoMarkBase: "../",
})}

${renderSectionStack([
  {
    headline: "A Comparison-Driven Buying Process.",
    paragraphs: [
      "Window replacement is rarely an impulse purchase. Homeowners typically compare window types, request multiple estimates, and research installers before committing. Search visibility needs to support each stage of that process, from early research to a final decision.",
      "Content that clearly explains products, process, and pricing expectations tends to serve this audience better than pages built around urgency alone.",
    ],
  },
  {
    headline: "Where We Focus for Window Installation Companies",
    paragraphs: ["Visibility strategies for window installers typically emphasize:"],
    tags: [
      "Local SEO and service-area pages",
      "Product comparison content",
      "Google Business Profile optimization",
      "Review strategy and warranty visibility",
      "Estimate and consultation pages",
      "Technical SEO",
      "AI search visibility for product questions",
    ],
  },
  {
    headline: "Product and Service Opportunities",
    paragraphs: ["Window installation search demand covers a range of products and related services, including:"],
    tags: [
      "Replacement windows",
      "New construction window installation",
      "Vinyl windows",
      "Wood windows",
      "Fiberglass windows",
      "Energy-efficient windows",
      "Patio doors",
      "Entry doors, as a secondary service",
      "Free estimates and consultations",
      "Financing options",
    ],
  },
  {
    headline: "What a Window Installation Strategy May Include",
    paragraphs: [
      "Depending on your current site, a strategy may include building clearer product and service pages, strengthening local SEO and Google Business Profile visibility, developing comparison-style content, and improving technical SEO. Any statements about energy savings must be supported and specific rather than general industry claims presented as guarantees.",
    ],
  },
  {
    headline: "Why Work With Water Buffalo Media",
    paragraphs: [
      "Window installation customers want clarity before they commit. We build a search presence that answers their questions directly, supports local competition, and positions your business clearly across Google Search, Google Maps, and AI-generated answers.",
    ],
  },
])}

${renderFaq(faqItems)}

${renderRelatedLinks("Related Industries", [
  { label: "Roofing and Siding Marketing", href: "roofing-siding-marketing" },
  { label: "Bathroom Remodeling Marketing", href: "bathroom-remodeling-marketing" },
  { label: "Painting Contractor Marketing", href: "painting-contractor-marketing" },
])}

${renderCta({
  headline: "Ready to Strengthen Your Window Installation Search Visibility?",
  body: "Request a free audit and we will review your current visibility across Google Search, Google Maps, and AI-generated answers.",
  primaryHref: "../contact",
})}
`;
