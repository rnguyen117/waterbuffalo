import {
  renderHero,
  renderBreadcrumbs,
  renderServiceCard,
  renderCta,
  organizationSchema,
  breadcrumbSchema,
  itemListSchema,
  SERVICES,
} from "../components.mjs";

export const path = "/services.html";
export const title = "SEO and Search Visibility Services | Water Buffalo Media";
export const description =
  "Explore Local SEO, National SEO, Global SEO, Generative Engine Optimization, Google Business Profile Optimization, and Technical SEO services.";

const trail = [{ label: "Home", href: "./" }, { label: "Services" }];

export const schemas = [
  organizationSchema(),
  breadcrumbSchema(trail),
  itemListSchema(
    SERVICES.map((s) => ({ name: s.name, href: s.href })),
    { name: "Services" }
  ),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "OUR SERVICES",
  headline: "Every Part of Search Visibility, Working Together.",
  body: "Search platforms evaluate your website, locations, content, reputation, structure, and authority as one connected system. Our services strengthen each layer while keeping the full search ecosystem in view.",
  compact: true,
})}

<section class="section">
  <div class="container">
    <div class="grid services__grid services__grid--expanded">
      ${SERVICES.map((s) => renderServiceCard(s, { expanded: true })).join("\n")}
    </div>
  </div>
</section>

<section class="section section--alt">
  <div class="container narrow">
    <h2 class="section-title reveal">Choose a Focused Service or Build a Complete Strategy.</h2>
    <p class="reveal">Some businesses need a specific technical correction. Others need a complete search foundation. We can address an individual priority or combine services into a coordinated visibility strategy.</p>
  </div>
</section>

${renderCta({
  headline: "Find the Weakest Point in Your Search Presence.",
})}
`;
