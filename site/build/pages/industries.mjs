import {
  renderHero,
  renderBreadcrumbs,
  renderIndustryCard,
  renderCta,
  organizationSchema,
  breadcrumbSchema,
  itemListSchema,
  INDUSTRIES,
} from "../components.mjs";

export const path = "/industries.html";
export const title = "Industry Marketing and SEO Services | Water Buffalo Media";
export const description =
  "Search visibility strategies built around how customers research and choose businesses in HVAC, plumbing, remodeling, roofing, and other service industries.";

const trail = [{ label: "Home", href: "index.html" }, { label: "Industries" }];

export const schemas = [
  organizationSchema(),
  breadcrumbSchema(trail),
  itemListSchema(
    INDUSTRIES.map((i) => ({ name: i.name, href: i.href })),
    { name: "Industries We Serve" }
  ),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "INDUSTRIES",
  headline: "Search Visibility Strategies Built for Your Industry.",
  body: "Different industries compete for attention in different ways. Water Buffalo Media develops search visibility strategies around how customers research, compare, and choose businesses within each market. Explore our industry-specific approach to Google Search, Google Maps, and AI-generated answers.",
  compact: true,
  hideActions: true,
})}

<section class="section">
  <div class="container">
    <p class="eyebrow reveal">Explore an Industry</p>
    <h2 class="section-title reveal">Search Behavior Looks Different in Every Market.</h2>
    <p class="section-lead reveal">Select an industry below to see how we approach visibility for that specific market, including the terminology, service categories, and customer questions that shape how people search.</p>
    <div class="grid industries__grid">
      ${INDUSTRIES.map((i) => renderIndustryCard(i)).join("\n")}
    </div>
  </div>
</section>

<section class="section section--alt">
  <div class="container narrow">
    <h2 class="section-title reveal">Why Industry Context Matters.</h2>
    <p class="reveal">A generic SEO strategy treats every business the same way. In practice, the way people search for a plumber during a burst pipe has almost nothing in common with the way they search for a kitchen remodeler planning a project six months out. Search intent, decision timelines, seasonal patterns, and the platforms customers rely on all shift by industry.</p>
    <p class="reveal">Google Maps weighs differently for a business built on same-day emergency calls than it does for one built on large, considered projects. AI-generated answers summarize industries differently depending on how clearly a business communicates its services, service area, and expertise. A strategy that ignores those differences produces generic content that struggles to rank and does not reflect how real customers make decisions.</p>
    <p class="reveal">We build industry context into the strategy from the start, rather than applying the same template to every business we work with.</p>
  </div>
</section>

<section class="section">
  <div class="container narrow">
    <h2 class="section-title reveal">Our Approach.</h2>
    <p class="reveal">For every industry we support, we start with the same foundation: a website search engines can crawl and understand, a Google Business Profile that accurately represents the business, and content that reflects real services, real service areas, and real customer questions.</p>
    <p class="reveal">From there, the emphasis shifts. Some industries depend most heavily on local proximity and emergency search volume. Others depend on visual proof, service-specific landing pages, and longer nurture content. We adjust technical SEO, local SEO, Google Business Profile optimization, content architecture, and AI search visibility work to match how your specific market actually searches, without resorting to fabricated statistics or guaranteed outcomes.</p>
    <p class="reveal">Our core services apply across every industry we support:</p>
    <ul class="checklist checklist--cols-2 reveal">
      <li>${checklistIcon()}<span>Local SEO</span></li>
      <li>${checklistIcon()}<span>Technical SEO</span></li>
      <li>${checklistIcon()}<span>Google Business Profile Optimization</span></li>
      <li>${checklistIcon()}<span>National SEO</span></li>
      <li>${checklistIcon()}<span>Generative Engine Optimization</span></li>
      <li>${checklistIcon()}<span>Global SEO</span></li>
    </ul>
  </div>
</section>

${renderCta({
  headline: "Not Sure Where Your Industry Fits?",
  body: "Request a free audit and we will review your current search presence in the context of your specific market.",
  secondaryLabel: "Explore Our Services",
  secondaryHref: "services.html",
})}
`;

function checklistIcon() {
  return '<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>';
}
