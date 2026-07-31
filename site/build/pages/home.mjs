import {
  renderHero,
  renderMarquee,
  renderCta,
  renderServiceCard,
  renderFeatureGrid,
  organizationSchema,
  SERVICES,
} from "../components.mjs";

export const path = "/";
export const title = "Water Buffalo Media | SEO, Local Search and AI Visibility";
export const description =
  "Build lasting visibility across Google Search, Google Maps, and AI platforms with technical SEO, local search strategy, content architecture, and generative engine optimization.";
export const schemas = [organizationSchema()];

export const bodyHtml = `
${renderHero({
  eyebrow: "SEARCH VISIBILITY, BUILT TO LAST",
  headline: "Built for Lasting Visibility.",
  body: "Water Buffalo Media helps businesses become easier to find, understand, and trust across Google Search, Google Maps, and AI-generated answers. We build the technical foundation, content architecture, and digital authority required for sustainable search growth.",
  secondaryLabel: "Explore Our Services",
  secondaryHref: "services.html",
  showBuffalo: true,
})}

${renderMarquee([
  "GOOGLE SEARCH",
  "GOOGLE MAPS",
  "AI OVERVIEWS",
  "CHATGPT",
  "GEMINI",
  "PERPLEXITY",
  "LOCAL SEARCH",
  "NATIONAL SEARCH",
  "GLOBAL SEARCH",
])}

<section class="section">
  <div class="container intro-section">
    <div class="intro-section__text">
      <p class="eyebrow reveal">Our Approach</p>
      <h2 class="section-title reveal">Search Is No Longer One Place.</h2>
      <p class="reveal">Customers now discover businesses through traditional search results, map listings, AI Overviews, chat platforms, and recommendation engines. Visibility depends on whether these systems can clearly understand your business, your expertise, your locations, and the value you provide.</p>
      <p class="reveal">Water Buffalo Media connects those pieces into one durable search strategy.</p>
    </div>
    <p class="intro-section__statement reveal">We do not build campaigns around isolated keywords. We build systems of relevance, authority, and trust.</p>
  </div>
</section>

<section class="section section--alt">
  <div class="container">
    <h2 class="section-title reveal" style="max-width:640px">A Stronger Foundation for Modern Search</h2>
    ${renderFeatureGrid(
      [
        {
          icon: "understood",
          title: "Be Understood",
          copy: "We organize your website, services, locations, content, and structured data so search engines can clearly interpret what your business does and who it serves.",
        },
        {
          icon: "trusted",
          title: "Be Trusted",
          copy: "We strengthen the signals that establish credibility, including topical depth, local relevance, technical consistency, entity relationships, and external authority.",
        },
        {
          icon: "discovered",
          title: "Be Discovered",
          copy: "We improve your visibility across organic search, map results, local discovery, and AI-generated recommendations.",
        },
      ],
      { columns: 3 }
    )}
  </div>
</section>

<section class="section" id="services">
  <div class="container">
    <p class="eyebrow reveal">What We Build</p>
    <h2 class="section-title reveal">One Search Strategy. Every Level of Visibility.</h2>
    <p class="section-lead reveal">Each service addresses a different part of the search ecosystem. Together, they create a complete visibility system designed to support long-term growth.</p>
    <div class="grid services__grid">
      ${SERVICES.map((s) => renderServiceCard(s)).join("\n")}
    </div>
  </div>
</section>

<section class="section section--dark philosophy">
  <img class="philosophy__mark" src="assets/buffalo-hero.png" alt="" aria-hidden="true" loading="lazy" width="798" height="884">
  <div class="container philosophy__inner">
    <p class="eyebrow reveal">Why the Water Buffalo</p>
    <h2 class="reveal">Strength Is Built Through Consistency.</h2>
    <p class="reveal">In Vietnamese culture, the water buffalo has long represented hard work, endurance, patience, and a close connection to community and the land.</p>
    <p class="reveal">Those same qualities shape our approach to search.</p>
    <p class="reveal">Strong visibility is rarely created through one dramatic change. It is built through steady technical improvement, thoughtful content, consistent local signals, and strategies designed to hold their value over time.</p>
    <p class="philosophy__closing reveal">We favor durable progress over temporary wins.</p>
  </div>
</section>

<section class="section" id="process">
  <div class="container">
    <p class="eyebrow reveal">Our Process</p>
    <h2 class="section-title reveal">A Clear Path From Confusion to Visibility</h2>
    ${renderFeatureGrid(
      [
        { title: "Understand", copy: "We study your business, website, customers, market, competitors, locations, and current search presence." },
        { title: "Build", copy: "We create the technical foundation, content structure, entity signals, and local relevance your business needs." },
        { title: "Strengthen", copy: "We expand authority through content, internal relationships, optimization, citations, links, and ongoing improvements." },
        { title: "Measure", copy: "We track visibility, qualified traffic, calls, conversions, rankings, and the performance of the assets that matter most." },
      ],
      { columns: 4, numbered: true }
    )}
  </div>
</section>

<section class="section section--alt">
  <div class="container differentiation">
    <h2 class="section-title reveal">Not More SEO Activity. Better Search Infrastructure.</h2>
    <p class="section-lead reveal">Many SEO campaigns produce reports, publish disconnected content, and track rankings without fixing the underlying system.</p>
    <p class="reveal">We focus on how every part of your search presence works together:</p>
    <ul class="checklist checklist--cols-2 reveal">
      <li>${featureCheck()}<span>Website architecture</span></li>
      <li>${featureCheck()}<span>Service and location relationships</span></li>
      <li>${featureCheck()}<span>Internal linking</span></li>
      <li>${featureCheck()}<span>Search intent</span></li>
      <li>${featureCheck()}<span>Technical performance</span></li>
      <li>${featureCheck()}<span>Google Business Profile signals</span></li>
      <li>${featureCheck()}<span>Structured data</span></li>
      <li>${featureCheck()}<span>Entity clarity</span></li>
      <li>${featureCheck()}<span>Topical authority</span></li>
      <li>${featureCheck()}<span>AI search readiness</span></li>
    </ul>
    <p class="differentiation__closing reveal">The result is not simply a collection of optimized pages. It is a stronger digital presence that search platforms can understand and trust.</p>
  </div>
</section>

${renderCta({
  headline: "Build Visibility That Can Carry Your Business Forward.",
  body: "Request a clear assessment of your current search presence, the obstacles limiting your visibility, and the strongest opportunities for improvement.",
  secondaryLabel: "Contact Water Buffalo Media",
  secondaryHref: "contact.html",
})}
`;

function featureCheck() {
  return '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>';
}
