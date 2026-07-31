import {
  renderHero,
  renderBreadcrumbs,
  renderFaq,
  organizationSchema,
  breadcrumbSchema,
  faqSchema,
} from "../components.mjs";

export const path = "/contact.html";
export const title = "Contact Water Buffalo Media";
export const description =
  "Contact Water Buffalo Media to request a search visibility audit or discuss Local SEO, Technical SEO, Google Business Profile optimization, and AI search strategy.";

const trail = [{ label: "Home", href: "index.html" }, { label: "Contact" }];

const faqItems = [
  {
    q: "What happens after I request an audit?",
    a: "We review your website, search presence, market, and stated goals. If there is a strong fit, we will contact you to discuss the most important opportunities and next steps.",
  },
  {
    q: "Is the audit really free?",
    a: "Yes. The initial audit is intended to identify major visibility issues and determine whether Water Buffalo Media is the right fit for your needs.",
  },
  {
    q: "Do you work with businesses outside the United States?",
    a: "Yes. We support local, national, and international search strategies.",
  },
  {
    q: "Can you work with my existing website team?",
    a: "Yes. We can provide strategy and recommendations or collaborate directly with developers, writers, designers, and internal marketing teams.",
  },
];

export const schemas = [
  organizationSchema(),
  breadcrumbSchema(trail),
  faqSchema(faqItems),
];

export const bodyHtml = `
${renderBreadcrumbs(trail)}
${renderHero({
  eyebrow: "CONTACT",
  headline: "Start With a Clearer View of Your Search Presence.",
  body: "Tell us about your business, your market, and the visibility challenges you are facing. We will review the opportunity and determine where stronger structure, relevance, or authority could make the greatest difference.",
  compact: true,
  hideActions: true,
})}

<section class="section contact-section">
  <div class="container contact-section__inner">
    <form class="contact-form" action="#" method="post">
      <h2 class="reveal">Request a Free Audit</h2>

      <div class="contact-form__grid">
        <div class="field">
          <label for="fullName">Full Name</label>
          <input id="fullName" name="fullName" type="text" autocomplete="name" required>
        </div>
        <div class="field">
          <label for="companyName">Company Name</label>
          <input id="companyName" name="companyName" type="text" autocomplete="organization" required>
        </div>
        <div class="field">
          <label for="email">Email Address</label>
          <input id="email" name="email" type="email" autocomplete="email" required>
        </div>
        <div class="field">
          <label for="phone">Phone Number</label>
          <input id="phone" name="phone" type="tel" autocomplete="tel">
        </div>
        <div class="field">
          <label for="website">Website URL</label>
          <input id="website" name="website" type="url" placeholder="yourcompany.com" required>
        </div>
        <div class="field">
          <label for="service">Primary Service Needed</label>
          <select id="service" name="service" required>
            <option value="" disabled selected>Select one</option>
            <option>Local SEO</option>
            <option>National SEO</option>
            <option>Global SEO</option>
            <option>Generative Engine Optimization</option>
            <option>Google Business Profile Optimization</option>
            <option>Technical SEO</option>
            <option>Complete Search Strategy</option>
            <option>Not Sure Yet</option>
          </select>
        </div>
        <div class="field">
          <label for="market">Target Market</label>
          <input id="market" name="market" type="text" placeholder="City, region, country, or national">
        </div>
        <div class="field">
          <label for="heard">How Did You Hear About Us?</label>
          <input id="heard" name="heard" type="text">
        </div>
        <div class="field field--full">
          <label for="goal">What Are You Trying to Improve?</label>
          <textarea id="goal" name="goal" rows="4" required></textarea>
        </div>
      </div>

      <button class="btn btn--primary btn--lg" type="submit">Request a Free Audit</button>
      <p class="contact-form__note">We will use this information to better understand your website and search presence. Submitting the form does not enroll you in recurring marketing messages.</p>
    </form>
  </div>
</section>

${renderFaq(faqItems)}
`;
