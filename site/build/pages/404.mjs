import { renderCta, organizationSchema } from "../components.mjs";

export const path = "/404.html";
export const title = "Page Not Found | Water Buffalo Media";
export const description = "The page you're looking for can't be found. Return to Water Buffalo Media to explore our Local, National, Global, and AI search services.";
export const schemas = [organizationSchema()];
export const noindex = true;

export const bodyHtml = `
<section class="hero hero--compact hero--404">
  <div class="hero__glow" aria-hidden="true"></div>
  <div class="hero__grid" aria-hidden="true"></div>
  <div class="container hero__inner">
    <p class="eyebrow reveal">Page Not Found</p>
    <h1 class="hero__title reveal">This Page Has Wandered Off the Path.</h1>
    <p class="hero__lead reveal">The page you're looking for may have moved or no longer exists. Steady progress means finding your footing again — start from the homepage or explore our services.</p>
    <div class="hero__actions reveal">
      <a class="btn btn--primary btn--lg" href="./">Return Home</a>
      <a class="btn btn--ghost-dark btn--lg" href="services">View Services</a>
    </div>
  </div>
</section>

${renderCta({
  headline: "Still Looking for Something Specific?",
  body: "Reach out and we'll help you find the right place to start.",
  primaryLabel: "Contact Water Buffalo Media",
  primaryHref: "contact",
})}
`;
