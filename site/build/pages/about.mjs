import {
  renderHero,
  renderBreadcrumbs,
  renderFeatureGrid,
  renderRelatedLinks,
  renderCta,
  renderChecklist,
  organizationSchema,
  breadcrumbSchema,
} from "../components.mjs";

export const path = "/about.html";
export const title = "About Water Buffalo Media | Built for Lasting Visibility";
export const description =
  "Learn how Water Buffalo Media combines technical precision, steady strategy, and values inspired by the Vietnamese water buffalo to build durable search visibility.";

const trail = [{ label: "Home", href: "index.html" }, { label: "About" }];

export const schemas = [organizationSchema(), breadcrumbSchema(trail)];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "ABOUT WATER BUFFALO MEDIA",
  headline: "Strong Foundations. Steady Progress.",
  body: "Water Buffalo Media was built around a simple belief: lasting search visibility comes from disciplined work, clear systems, and strategies strong enough to endure change.",
  compact: true,
})}

<section class="section section--dark philosophy">
  <img class="philosophy__mark" src="assets/buffalo-hero.png" alt="" aria-hidden="true" loading="lazy" width="798" height="884">
  <div class="container philosophy__inner">
    <p class="eyebrow reveal">Our Philosophy</p>
    <h2 class="reveal">Why Water Buffalo?</h2>
    <p class="reveal">The water buffalo holds a meaningful place in Vietnamese history and rural life. It represents endurance, patience, strength, hard work, and a deep connection to community.</p>
    <p class="reveal">It is not an animal defined by speed or spectacle. Its strength comes from consistency, resilience, and the ability to keep moving forward through difficult conditions.</p>
    <p class="philosophy__closing reveal">That philosophy shapes how we approach search.</p>
  </div>
</section>

<section class="section">
  <div class="container narrow">
    <h2 class="section-title reveal">We Do Not Chase Every Algorithm Update.</h2>
    <p class="reveal">Search changes constantly. Platforms evolve, ranking systems shift, and new forms of discovery emerge.</p>
    <p class="reveal">Businesses still need the same fundamentals:</p>
    ${renderChecklist(
      [
        "A website that can be understood",
        "Information people can trust",
        "Clear services and locations",
        "Strong technical structure",
        "Useful content",
        "Consistent authority",
        "A strategy that can adapt",
      ],
      2
    )}
    <p class="reveal">We build around those fundamentals.</p>
  </div>
</section>

<section class="section section--alt">
  <div class="container">
    <h2 class="section-title reveal" style="max-width:520px">Our Values</h2>
    ${renderFeatureGrid(
      [
        { title: "Strength", copy: "We build strategies on solid technical and informational foundations." },
        { title: "Patience", copy: "We understand that meaningful authority is earned over time." },
        { title: "Endurance", copy: "We create systems designed to remain useful through platform and algorithm changes." },
        { title: "Reliability", copy: "We communicate clearly, document our work, and focus on what can actually be measured." },
        { title: "Community", copy: "We help businesses become more visible to the customers and markets they serve." },
        { title: "Steady Progress", copy: "We prioritize consistent improvement over short-lived spikes." },
      ],
      { columns: 3, numbered: true }
    )}
  </div>
</section>

<section class="section">
  <div class="container narrow">
    <h2 class="section-title reveal">Modern Search Requires a Wider View.</h2>
    <p class="reveal">SEO is no longer limited to traditional rankings. Businesses must now be understood across organic search, local results, map listings, structured data, knowledge systems, and AI-generated answers.</p>
    <p class="reveal">Water Buffalo Media brings those areas together into one visibility strategy.</p>
  </div>
</section>

${renderRelatedLinks("Continue Exploring", [
  { label: "Our Services", href: "services.html" },
  { label: "Generative Engine Optimization", href: "ai-search.html" },
  { label: "Contact", href: "contact.html" },
])}

${renderCta({
  headline: "Build Something Stronger Than a Temporary Ranking.",
})}
`;
