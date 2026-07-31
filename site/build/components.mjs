// Shared page components for the Water Buffalo Media static site.
// Plain template-literal functions — no framework, no build dependency.

export const SITE_URL = "https://waterbuffalomedia.com";
export const SITE_NAME = "Water Buffalo Media";

export const NAV_LINKS = [
  { label: "Home", href: "index.html" },
  {
    label: "Services",
    href: "services.html",
    children: [
      { label: "Local SEO", href: "local-seo.html" },
      { label: "National SEO", href: "national-seo.html" },
      { label: "Global SEO", href: "global-seo.html" },
      { label: "AI Search", href: "ai-search.html" },
      { label: "Google Business Profile", href: "google-business-profile.html" },
      { label: "Technical SEO", href: "technical-seo.html" },
    ],
  },
  { label: "About", href: "about.html" },
  { label: "Contact", href: "contact.html" },
];

export const SERVICES = [
  {
    slug: "local-seo",
    href: "local-seo.html",
    name: "Local SEO",
    navLabel: "Local SEO",
    title: "Own Your Service Area",
    description:
      "Build stronger visibility in the cities, towns, and neighborhoods that matter most to your business.",
    linkText: "Explore Local SEO",
    icon: "pin",
    capabilities: [
      "Service-area architecture",
      "Google Business Profile optimization",
      "Citation consistency",
      "Review strategy",
      "Local schema",
    ],
  },
  {
    slug: "national-seo",
    href: "national-seo.html",
    name: "National SEO",
    navLabel: "National SEO",
    title: "Build Authority That Scales",
    description:
      "Create the content depth, website structure, and industry authority required to compete across larger markets.",
    linkText: "Explore National SEO",
    icon: "scale",
    capabilities: [
      "National keyword strategy",
      "Content architecture",
      "Topic clusters",
      "Internal linking systems",
      "Technical SEO",
    ],
  },
  {
    slug: "global-seo",
    href: "global-seo.html",
    name: "Global SEO",
    navLabel: "Global SEO",
    title: "Expand Without Losing Clarity",
    description:
      "Reach international markets with search strategies built around language, location, culture, and technical precision.",
    linkText: "Explore Global SEO",
    icon: "globe",
    capabilities: [
      "International keyword research",
      "Hreflang implementation",
      "International URL structure",
      "Localized content planning",
      "International technical audits",
    ],
  },
  {
    slug: "ai-search",
    href: "ai-search.html",
    name: "Generative Engine Optimization",
    navLabel: "AI Search",
    title: "Be Recognized by AI Search",
    description:
      "Help AI platforms understand, reference, and recommend your business through stronger entities, content, structure, and authority.",
    linkText: "Explore AI Search",
    icon: "spark",
    capabilities: [
      "Entity clarity",
      "Structured data",
      "Semantic content",
      "Expert signals",
      "AI visibility monitoring",
    ],
  },
  {
    slug: "google-business-profile",
    href: "google-business-profile.html",
    name: "Google Business Profile Optimization",
    navLabel: "Google Business Profile",
    title: "Strengthen Your Local Presence",
    description:
      "Turn your business profile into a stronger source of local visibility, customer trust, calls, and direction requests.",
    linkText: "Explore GBP Optimization",
    icon: "building",
    capabilities: [
      "Primary and secondary categories",
      "Business description",
      "Review strategy",
      "Google Posts",
      "Duplicate listing issues",
    ],
  },
  {
    slug: "technical-seo",
    href: "technical-seo.html",
    name: "Technical SEO",
    navLabel: "Technical SEO",
    title: "Build a Website Search Engines Can Read",
    description:
      "Resolve the structural, performance, crawling, and indexing issues that limit visibility.",
    linkText: "Explore Technical SEO",
    icon: "code",
    capabilities: [
      "Crawlability",
      "Core Web Vitals",
      "Structured data",
      "Internal linking",
      "XML sitemaps",
    ],
  },
];

const CTA_LABEL = "Request a Free Audit";

function esc(str = "") {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function svgIcon(name) {
  const icons = {
    search:
      '<circle cx="10.5" cy="10.5" r="6.5"/><line x1="20" y1="20" x2="15.3" y2="15.3"/>',
    scale:
      '<path d="M4 4h11l5 5v11H4z"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="14" y2="16"/>',
    globe:
      '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><line x1="3" y1="12" x2="21" y2="12"/>',
    spark:
      '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"/><circle cx="12" cy="12" r="3"/>',
    pin: '<path d="M12 21s-7-6.1-7-11.5A7 7 0 0 1 19 9.5C19 14.9 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.3"/>',
    gear: '<circle cx="12" cy="12" r="3.2"/><path d="M12 3.5v2.4M12 18.1v2.4M20.5 12h-2.4M5.9 12H3.5M17.7 6.3l-1.7 1.7M8 16l-1.7 1.7M17.7 17.7 16 16M8 8 6.3 6.3"/>',
    understood: '<path d="M4 5h16v11H7l-3 3z"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="12" x2="13" y2="12"/>',
    trusted: '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/>',
    discovered: '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.2" y2="16.2"/>',
    check: '<path d="M5 13l4 4L19 7"/>',
    building:
      '<rect x="5" y="3" width="10" height="18"/><rect x="15" y="9" width="5" height="12"/><line x1="8" y1="7" x2="8" y2="7.01"/><line x1="12" y1="7" x2="12" y2="7.01"/><line x1="8" y1="11" x2="8" y2="11.01"/><line x1="12" y1="11" x2="12" y2="11.01"/><line x1="8" y1="15" x2="8" y2="15.01"/><line x1="12" y1="15" x2="12" y2="15.01"/>',
    code: '<polyline points="8 6 3 12 8 18"/><polyline points="16 6 21 12 16 18"/>',
    compass: '<circle cx="12" cy="12" r="9"/><polygon points="15 9 13.5 13.5 9 15 10.5 10.5 15 9"/>',
  };
  return `<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.check}</svg>`;
}

// ---------------------------------------------------------------
// <head>
// ---------------------------------------------------------------
export function renderHead({
  title,
  description,
  path,
  schemas = [],
  ogType = "website",
  noindex = false,
  inlineCss = "",
}) {
  const canonical = `${SITE_URL}${path}`;
  const schemaTags = schemas
    .map((s) => `<script type="application/ld+json">${JSON.stringify(s)}</script>`)
    .join("\n");

  return `<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#060708">
<style>${inlineCss}</style>
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
${noindex ? '<meta name="robots" content="noindex, follow">' : ""}
<link rel="canonical" href="${canonical}">

<meta property="og:type" content="${ogType}">
<meta property="og:site_name" content="${SITE_NAME}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${canonical}">
<meta property="og:image" content="${SITE_URL}/assets/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(title)}">
<meta name="twitter:description" content="${esc(description)}">
<meta name="twitter:image" content="${SITE_URL}/assets/og-image.png">

<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
${schemaTags}`;
}

// ---------------------------------------------------------------
// Organization schema (site-wide)
// ---------------------------------------------------------------
export function organizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": SITE_NAME,
    "url": SITE_URL,
    "logo": `${SITE_URL}/assets/favicon.svg`,
    "description":
      "Water Buffalo Media is a search visibility agency that engineers authority across Google Search, Google Maps, and AI-generated search experiences.",
    "sameAs": [],
  };
}

export function serviceSchema({ name, description, path, areaServed = "Worldwide" }) {
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    "serviceType": name,
    "name": name,
    "description": description,
    "provider": { "@type": "Organization", "name": SITE_NAME, "url": SITE_URL },
    "areaServed": areaServed,
    "url": `${SITE_URL}${path}`,
  };
}

export function breadcrumbSchema(trail) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": trail.map((item, i) => ({
      "@type": "ListItem",
      "position": i + 1,
      "name": item.label,
      "item": item.href ? `${SITE_URL}${item.href}` : undefined,
    })),
  };
}

export function faqSchema(items) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": items.map((it) => ({
      "@type": "Question",
      "name": it.q,
      "acceptedAnswer": { "@type": "Answer", "text": it.a },
    })),
  };
}

// ---------------------------------------------------------------
// Header / Nav
// ---------------------------------------------------------------
function normPath(p) {
  return p === "/" ? "index.html" : p.replace(/^\//, "");
}

export function renderHeader(currentPath) {
  const current = normPath(currentPath);
  const isServicesGroup = SERVICES.some((s) => s.href === current) || current === "services.html";

  const desktopLinks = NAV_LINKS.map((link) => {
    const active = link.href === current || (link.children && isServicesGroup);
    if (link.children) {
      return `<details class="nav-dropdown">
        <summary class="${active ? "is-active" : ""}">${link.label}<svg class="nav-dropdown__chevron" viewBox="0 0 12 8" width="10" height="7" aria-hidden="true"><path d="M1 1l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></summary>
        <div class="nav-dropdown__panel">
          <a href="${link.href}">Services Overview</a>
          ${link.children.map((c) => `<a href="${c.href}" class="${c.href === current ? "is-active" : ""}">${c.label}</a>`).join("\n")}
        </div>
      </details>`;
    }
    return `<a href="${link.href}" class="${active ? "is-active" : ""}">${link.label}</a>`;
  }).join("\n");

  const mobileLinks = NAV_LINKS.map((link) => {
    if (link.children) {
      return `<details class="mobile-nav__dropdown">
        <summary>${link.label}</summary>
        <div class="mobile-nav__dropdown-panel">
          <a href="${link.href}">Services Overview</a>
          ${link.children.map((c) => `<a href="${c.href}">${c.label}</a>`).join("\n")}
        </div>
      </details>`;
    }
    return `<a href="${link.href}">${link.label}</a>`;
  }).join("\n");

  return `<header class="site-header">
  <div class="container site-header__inner">
    <a class="brand" href="index.html" aria-label="${SITE_NAME} home">
      ${brandGlyph()}
      <span class="brand__word">Water Buffalo <em>Media</em></span>
    </a>

    <nav class="nav" aria-label="Primary">
      ${desktopLinks}
    </nav>

    <a class="btn btn--primary btn--sm nav__cta" href="contact.html">${CTA_LABEL}</a>

    <button class="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="mobile-nav">
      <span></span><span></span><span></span>
    </button>
  </div>

  <div class="mobile-nav" id="mobile-nav" hidden>
    ${mobileLinks}
    <a class="btn btn--primary" href="contact.html">${CTA_LABEL}</a>
  </div>
</header>`;
}

function brandGlyph() {
  return `<svg class="brand__glyph" viewBox="0 0 64 64" width="28" height="28" aria-hidden="true">
        <polygon points="32,6 54,16 58,32 50,46 32,58 14,46 6,32 10,16" fill="none" stroke="#2E6BFF" stroke-width="2"/>
        <polygon points="32,16 44,22 46,32 40,42 32,48 24,42 18,32 20,22" fill="#12131a"/>
        <polygon points="32,16 44,22 32,32" fill="#2E6BFF"/>
        <polygon points="32,16 32,32 20,22" fill="#1c3b82"/>
        <polygon points="32,32 46,32 40,42 32,48" fill="#1f4fc4"/>
        <polygon points="32,32 32,48 24,42 18,32" fill="#182a52"/>
      </svg>`;
}

// ---------------------------------------------------------------
// Footer
// ---------------------------------------------------------------
export function renderFooter() {
  return `<footer class="site-footer">
  <div class="container footer__top">
    <div class="footer__brand">
      <a class="brand" href="index.html">
        ${brandGlyph()}
        <span class="brand__word">Water Buffalo <em>Media</em></span>
      </a>
      <h2 class="footer__headline">Built for Lasting Visibility.</h2>
      <p>Water Buffalo Media helps businesses build durable visibility across Google Search, Google Maps, and emerging AI search platforms. Our work is grounded in strong technical foundations, thoughtful strategy, and steady long-term progress.</p>
      <a class="btn btn--primary" href="contact.html">${CTA_LABEL}</a>
    </div>

    <nav class="footer__col" aria-label="Site">
      <h4>Site</h4>
      <a href="index.html">Home</a>
      <a href="about.html">About</a>
      <a href="services.html">Services</a>
      <a href="contact.html">Contact</a>
      <a href="privacy.html">Privacy Policy</a>
    </nav>

    <nav class="footer__col" aria-label="Services">
      <h4>Services</h4>
      <a href="local-seo.html">Local SEO</a>
      <a href="national-seo.html">National SEO</a>
      <a href="global-seo.html">Global SEO</a>
      <a href="ai-search.html">Generative Engine Optimization</a>
      <a href="google-business-profile.html">Google Business Profile Optimization</a>
      <a href="technical-seo.html">Technical SEO</a>
    </nav>
  </div>

  <div class="container footer__bottom">
    <p>&copy; 2026 Water Buffalo Media. All rights reserved.</p>
    <p><a href="#top">Back to top ↑</a></p>
  </div>
</footer>`;
}

// ---------------------------------------------------------------
// Breadcrumbs
// ---------------------------------------------------------------
export function renderBreadcrumbs(trail) {
  const items = trail
    .map((item, i) => {
      const isLast = i === trail.length - 1;
      if (isLast || !item.href) {
        return `<span aria-current="page">${esc(item.label)}</span>`;
      }
      return `<a href="${item.href}">${esc(item.label)}</a>`;
    })
    .join('<span class="breadcrumbs__sep" aria-hidden="true">/</span>');

  return `<nav class="breadcrumbs" aria-label="Breadcrumb"><div class="container">${items}</div></nav>`;
}

// ---------------------------------------------------------------
// Hero
// ---------------------------------------------------------------
export function renderHero({ eyebrow, headline, body, primaryLabel = CTA_LABEL, primaryHref = "contact.html", secondaryLabel, secondaryHref, showBuffalo = false, compact = false, hideActions = false }) {
  return `<section class="hero${compact ? " hero--compact" : ""}">
    <div class="hero__glow" aria-hidden="true"></div>
    ${showBuffalo ? `<img class="hero__buffalo" src="assets/buffalo-hero.png" alt="" aria-hidden="true" loading="eager" fetchpriority="high" width="798" height="884">` : ""}
    <div class="hero__grid" aria-hidden="true"></div>

    <div class="container hero__inner">
      <p class="eyebrow reveal">${esc(eyebrow)}</p>
      <h1 class="hero__title reveal">${headline}</h1>
      <p class="hero__lead reveal">${body}</p>
      ${
        hideActions
          ? ""
          : `<div class="hero__actions reveal">
        <a class="btn btn--primary btn--lg" href="${primaryHref}">${primaryLabel}</a>
        ${secondaryLabel ? `<a class="btn btn--ghost-dark btn--lg" href="${secondaryHref}">${secondaryLabel}</a>` : ""}
      </div>`
      }
    </div>
  </section>`;
}

// ---------------------------------------------------------------
// Marquee (dark scrolling strip, homepage only — keeps the fold solid
// black beneath the hero and echoes the surfaces we build visibility on)
// ---------------------------------------------------------------
export function renderMarquee(items) {
  const spans = items.map((it) => `<span>${esc(it)}</span>`).join("");
  return `<section class="marquee" aria-label="Where we build visibility">
    <div class="marquee__track">${spans}${spans}</div>
  </section>`;
}

// ---------------------------------------------------------------
// CTA section
// ---------------------------------------------------------------
export function renderCta({ headline, body, primaryLabel = CTA_LABEL, primaryHref = "contact.html", secondaryLabel, secondaryHref }) {
  return `<section class="section cta-section">
    <div class="container cta-section__inner">
      <h2 class="reveal">${esc(headline)}</h2>
      ${body ? `<p class="reveal">${esc(body)}</p>` : ""}
      <div class="cta-section__actions reveal">
        <a class="btn btn--primary btn--lg" href="${primaryHref}">${primaryLabel}</a>
        ${secondaryLabel ? `<a class="btn btn--ghost btn--lg" href="${secondaryHref}">${secondaryLabel}</a>` : ""}
      </div>
    </div>
  </section>`;
}

// ---------------------------------------------------------------
// Service card
// ---------------------------------------------------------------
export function renderServiceCard(service, { expanded = false } = {}) {
  const bullets = expanded && service.capabilities
    ? `<ul class="service-card__bullets">${service.capabilities.map((c) => `<li>${svgIcon("check")}${esc(c)}</li>`).join("")}</ul>`
    : "";
  return `<article class="card service-card reveal">
    <span class="card__icon" aria-hidden="true">${svgIcon(service.icon || "search")}</span>
    <h3>${esc(service.name)}</h3>
    <p class="service-card__headline">${esc(service.title)}</p>
    <p>${esc(service.description)}</p>
    ${bullets}
    <a class="service-card__link" href="${service.href}">${esc(service.linkText)} <span aria-hidden="true">&rarr;</span></a>
  </article>`;
}

// ---------------------------------------------------------------
// FAQ
// ---------------------------------------------------------------
export function renderFaq(items) {
  return `<section class="section faq" id="faq">
    <div class="container">
      <p class="eyebrow reveal">Questions</p>
      <h2 class="section-title reveal">Frequently Asked Questions</h2>
      <div class="faq__list">
        ${items
          .map(
            (it, i) => `<details class="faq__item reveal"${i === 0 ? " open" : ""}>
          <summary>${esc(it.q)}<svg class="faq__chevron" viewBox="0 0 12 8" width="12" height="8" aria-hidden="true"><path d="M1 1l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></summary>
          <p>${esc(it.a)}</p>
        </details>`
          )
          .join("\n")}
      </div>
    </div>
  </section>`;
}

// ---------------------------------------------------------------
// Generic list/feature helpers
// ---------------------------------------------------------------
export function renderChecklist(items, columns = 2) {
  return `<ul class="checklist checklist--cols-${columns}">
    ${items.map((it) => `<li>${svgIcon("check")}<span>${esc(it)}</span></li>`).join("\n")}
  </ul>`;
}

export function renderFeatureGrid(items, { columns = 3, numbered = false } = {}) {
  return `<div class="feature-grid feature-grid--cols-${columns}">
    ${items
      .map(
        (it, i) => `<div class="feature-card reveal">
      ${numbered ? `<span class="feature-card__num">${String(i + 1).padStart(2, "0")}</span>` : `<span class="feature-card__icon" aria-hidden="true">${svgIcon(it.icon || "check")}</span>`}
      <h3>${esc(it.title)}</h3>
      <p>${esc(it.copy)}</p>
    </div>`
      )
      .join("\n")}
  </div>`;
}

// ---------------------------------------------------------------
// Generic inner-page section stack (used by the six service pages)
// ---------------------------------------------------------------
export function renderSectionStack(sections) {
  return sections
    .map((sec, i) => {
      const alt = i % 2 === 1;
      const listMarkup = sec.list
        ? renderChecklist(sec.list, sec.listColumns || 2)
        : "";
      const paras = (sec.paragraphs || [])
        .map((p) => `<p class="reveal">${p}</p>`)
        .join("\n");
      return `<section class="section${alt ? " section--alt" : ""}">
        <div class="container${sec.narrow ? " narrow" : ""}">
          <h2 class="section-title reveal">${esc(sec.headline)}</h2>
          ${paras}
          ${listMarkup}
        </div>
      </section>`;
    })
    .join("\n");
}

export function renderRelatedLinks(title, links) {
  return `<section class="section related-links">
    <div class="container">
      <h2 class="reveal">${esc(title)}</h2>
      <div class="related-links__grid reveal">
        ${links
          .map(
            (l) =>
              `<a class="related-links__item" href="${l.href}">${esc(l.label)} <span aria-hidden="true">&rarr;</span></a>`
          )
          .join("\n")}
      </div>
    </div>
  </section>`;
}

export { svgIcon, esc, CTA_LABEL };

// ---------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------
export function renderPage({ path, title, description, schemas = [], bodyHtml, noindex = false, inlineCss = "" }) {
  return `<!doctype html>
<html lang="en">
<head>
${renderHead({ title, description, path, schemas, noindex, inlineCss })}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
${renderHeader(path)}
<main id="main">
${bodyHtml}
</main>
${renderFooter()}
<script src="js/main.js"></script>
</body>
</html>
`;
}
