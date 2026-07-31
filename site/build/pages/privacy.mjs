import { renderBreadcrumbs, organizationSchema, breadcrumbSchema } from "../components.mjs";

export const path = "/privacy.html";
export const title = "Privacy Policy | Water Buffalo Media";
export const description =
  "Read the Water Buffalo Media privacy policy, including how contact form submissions, analytics, cookies, and third-party services are handled.";

const trail = [{ label: "Home", href: "index.html" }, { label: "Privacy Policy" }];

export const schemas = [organizationSchema(), breadcrumbSchema(trail)];

export const bodyHtml = `
${renderBreadcrumbs(trail)}

<section class="section">
  <div class="container narrow legal">
    <p class="eyebrow reveal">Privacy Policy</p>
    <h1 class="section-title reveal">Privacy Policy</h1>
    <p class="legal__updated reveal">Last updated: [Insert Effective Date]</p>

    <p class="reveal">This Privacy Policy explains how Water Buffalo Media ("Water Buffalo Media," "we," "us," or "our") collects, uses, and protects information when you visit this website or submit information through it.</p>

    <h2 class="reveal">Information We Collect</h2>
    <p class="reveal">We may collect information you voluntarily provide to us, as well as information collected automatically when you browse this website, such as device, browser, and usage data.</p>

    <h2 class="reveal">Contact Form Submissions</h2>
    <p class="reveal">When you submit an audit request or contact form, we collect the information provided in that form, which may include your name, company name, email address, phone number, website URL, target market, and details about your search visibility goals. We use this information solely to evaluate your request, respond to your inquiry, and, if appropriate, propose a working relationship.</p>

    <h2 class="reveal">Analytics</h2>
    <p class="reveal">We may use analytics tools to understand how visitors use this website, including pages viewed, time on site, and general geographic and device information. This data is used in aggregate to improve the website and is not used to personally identify individual visitors.</p>

    <h2 class="reveal">Cookies</h2>
    <p class="reveal">This website may use cookies or similar technologies to support core functionality and analytics. You can control or disable cookies through your browser settings. Disabling cookies may affect certain features of the website.</p>

    <h2 class="reveal">Third-Party Services</h2>
    <p class="reveal">We may use third-party service providers to support website hosting, analytics, and form processing. These providers may process information on our behalf and are expected to safeguard it in accordance with applicable law. We do not sell personal information to third parties.</p>

    <h2 class="reveal">Data Retention</h2>
    <p class="reveal">We retain information submitted through this website for as long as reasonably necessary to respond to inquiries, maintain business records, and comply with legal obligations, after which it is deleted or anonymized.</p>

    <h2 class="reveal">Your Rights</h2>
    <p class="reveal">Depending on your location, you may have the right to request access to, correction of, or deletion of the personal information we hold about you. To make a request, please use the contact information below.</p>

    <h2 class="reveal">Contact Information</h2>
    <p class="reveal">If you have questions about this Privacy Policy or how your information is handled, please contact us at:</p>
    <ul class="legal__contact reveal">
      <li>Email: [Insert Business Email Address]</li>
      <li>Phone: [Insert Business Phone Number]</li>
      <li>Mailing Address: [Insert Business Mailing Address]</li>
    </ul>

    <p class="reveal">This Privacy Policy may be updated periodically. Changes will be reflected on this page.</p>
  </div>
</section>
`;
