// Shared page components for the Water Buffalo Media static site.
// Plain template-literal functions — no framework, no build dependency.

export const SITE_URL = "https://www.waterbuffalomedia.com";
export const SITE_NAME = "Water Buffalo Media";

// page.path always keeps its .html suffix (build.mjs needs that to know
// which physical file to write), but Cloudflare Pages serves the
// extensionless URL directly with a 200 — the redirect only fires the
// other way around, from the .html URL to the clean one. So every
// public-facing URL (canonical, OG, sitemap, schema) should be built
// from the clean form, not the raw file path.
export function publicUrlPath(path) {
  if (path === "/" || path === "/index.html") return "/";
  return path.replace(/\.html$/, "");
}

export const NAV_LINKS = [
  { label: "Home", href: "./" },
  {
    label: "Services",
    href: "services",
    children: [
      { label: "Local SEO", href: "local-seo" },
      { label: "National SEO", href: "national-seo" },
      { label: "Global SEO", href: "global-seo" },
      { label: "AI Search", href: "ai-search" },
      { label: "Google Business Profile", href: "google-business-profile" },
      { label: "Technical SEO", href: "technical-seo" },
    ],
  },
  {
    label: "Industries",
    href: "industries",
    children: [
      { label: "HVAC", href: "industries/hvac-marketing" },
      { label: "Pest Control", href: "industries/pest-control-marketing" },
      { label: "Bathroom Remodeling", href: "industries/bathroom-remodeling-marketing" },
      { label: "Roofing & Siding", href: "industries/roofing-siding-marketing" },
      { label: "Window Installation", href: "industries/window-installation-marketing" },
      { label: "Plumbing", href: "industries/plumbing-marketing" },
      { label: "Electrical", href: "industries/electrical-contractor-marketing" },
      { label: "Kitchen Remodeling", href: "industries/kitchen-remodeling-marketing" },
      { label: "Landscaping", href: "industries/landscaping-marketing" },
      { label: "Painting", href: "industries/painting-contractor-marketing" },
      { label: "Financial Services", href: "industries/financial-services-marketing" },
      { label: "Legal Services", href: "industries/legal-services-marketing" },
      { label: "Healthcare Providers", href: "industries/healthcare-provider-marketing" },
      { label: "SaaS & Technology", href: "industries/saas-technology-marketing" },
    ],
  },
  { label: "About", href: "about" },
  { label: "Contact", href: "contact" },
];

export const INDUSTRIES = [
  {
    slug: "hvac-marketing",
    href: "industries/hvac-marketing",
    name: "HVAC",
    title: "HVAC Marketing",
    description:
      "Search visibility built around seasonal demand, emergency repair searches, and year-round Google Maps presence.",
    icon: "gear",
  },
  {
    slug: "pest-control-marketing",
    href: "industries/pest-control-marketing",
    name: "Pest Control",
    title: "Pest Control Marketing",
    description:
      "Capture high-intent, problem-driven searches with clear local visibility and trust signals for treatment services.",
    icon: "discovered",
  },
  {
    slug: "bathroom-remodeling-marketing",
    href: "industries/bathroom-remodeling-marketing",
    name: "Bathroom Remodeling",
    title: "Bathroom Remodeling Marketing",
    description:
      "Support long research cycles with visual proof, service-specific pages, and durable local authority.",
    icon: "understood",
  },
  {
    slug: "roofing-siding-marketing",
    href: "industries/roofing-siding-marketing",
    name: "Roofing & Siding",
    title: "Roofing & Siding Marketing",
    description:
      "Compete in dense local markets with clear service architecture for repair, replacement, and storm-driven demand.",
    icon: "building",
  },
  {
    slug: "window-installation-marketing",
    href: "industries/window-installation-marketing",
    name: "Window Installation",
    title: "Window Installation Marketing",
    description:
      "Reach ready-to-buy homeowners comparing window types, installers, and estimates in your service area.",
    icon: "compass",
  },
  {
    slug: "plumbing-marketing",
    href: "industries/plumbing-marketing",
    name: "Plumbing",
    title: "Plumbing Marketing",
    description:
      "Balance urgent emergency searches with planned service visibility across residential and commercial work.",
    icon: "gear",
  },
  {
    slug: "electrical-contractor-marketing",
    href: "industries/electrical-contractor-marketing",
    name: "Electrical",
    title: "Electrical Contractor Marketing",
    description:
      "Build local demand around panel upgrades, EV chargers, and licensed electrical work customers can trust.",
    icon: "spark",
  },
  {
    slug: "kitchen-remodeling-marketing",
    href: "industries/kitchen-remodeling-marketing",
    name: "Kitchen Remodeling",
    title: "Kitchen Remodeling Marketing",
    description:
      "Support high-value, considered projects with visual proof, clear budgets, and consultation-focused pages.",
    icon: "building",
  },
  {
    slug: "landscaping-marketing",
    href: "industries/landscaping-marketing",
    name: "Landscaping",
    title: "Landscaping Marketing",
    description:
      "Grow visibility for both recurring maintenance and large seasonal installation and design projects.",
    icon: "globe",
  },
  {
    slug: "painting-contractor-marketing",
    href: "industries/painting-contractor-marketing",
    name: "Painting",
    title: "Painting Contractor Marketing",
    description:
      "Turn seasonal and project-based search interest into estimate requests with clear service visibility.",
    icon: "trusted",
  },
  {
    slug: "financial-services-marketing",
    href: "industries/financial-services-marketing",
    name: "Financial Services",
    title: "Financial Services Marketing",
    description:
      "Build national authority and local branch visibility for advisory, wealth management, and accounting firms.",
    icon: "scale",
  },
  {
    slug: "legal-services-marketing",
    href: "industries/legal-services-marketing",
    name: "Legal Services",
    title: "Legal Services Marketing",
    description:
      "Compete for high-value practice area searches with authoritative content and strong local and national visibility.",
    icon: "trusted",
  },
  {
    slug: "healthcare-provider-marketing",
    href: "industries/healthcare-provider-marketing",
    name: "Healthcare Providers",
    title: "Healthcare Provider Marketing",
    description:
      "Support patient research and appointment decisions with clear local visibility and credible service content.",
    icon: "understood",
  },
  {
    slug: "saas-technology-marketing",
    href: "industries/saas-technology-marketing",
    name: "SaaS & Technology",
    title: "SaaS and Technology Marketing",
    description:
      "Build global and national search authority for software companies competing beyond any single location.",
    icon: "code",
  },
];

export const SERVICES = [
  {
    slug: "local-seo",
    href: "local-seo",
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
    href: "national-seo",
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
    href: "global-seo",
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
    href: "ai-search",
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
    href: "google-business-profile",
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
    href: "technical-seo",
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
  const canonical = `${SITE_URL}${publicUrlPath(path)}`;
  const base = basePath(path);
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

<link rel="icon" href="${base}assets/favicon.svg" type="image/svg+xml">

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
    "logo": `${SITE_URL}/assets/logo-mark.png`,
    "email": "contact@waterbuffalomedia.com",
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
    "url": `${SITE_URL}${publicUrlPath(path)}`,
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
      // Every breadcrumb parent link in this site points to a root-level
      // page, so stripping any leading "../" segments (used from one-
      // directory-deep pages like /industries/*) and prefixing SITE_URL
      // reconstructs the correct absolute URL regardless of how deep the
      // current page sits. Without this, SITE_URL was being concatenated
      // directly onto the relative href (e.g. "./"), producing
      // malformed URLs like "https://site.comindex".
      "item": item.href
        ? `${SITE_URL}/${item.href.replace(/^(\.\.\/)+/, "").replace(/^\.\/$/, "")}`
        : undefined,
    })),
  };
}

export function itemListSchema(items, { name } = {}) {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    ...(name ? { name } : {}),
    "itemListElement": items.map((it, i) => ({
      "@type": "ListItem",
      "position": i + 1,
      "name": it.name,
      "url": `${SITE_URL}/${it.href}`,
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
// Normalizes a raw page.path (e.g. "/local-seo.html", "/") into the
// same extensionless form used by NAV_LINKS/SERVICES/INDUSTRIES hrefs,
// purely so the two can be compared for active-link highlighting.
function normPath(p) {
  if (p === "/") return "./";
  return p.replace(/^\//, "").replace(/\.html$/, "");
}

// The site was flat (every page at site root) until the /industries/*
// pages introduced one level of nesting. Header, footer, favicon, and
// the main.js <script> tag all reference root-relative paths like
// "contact" or "assets/...", which only resolve correctly from a
// page actually sitting at the root. basePath() computes the "../"
// prefix needed so those same root-relative values still resolve
// correctly from a page nested one (or more) directories deep.
// Deliberately computed from the raw path (not normPath()'s output,
// which rewrites "/" to "./" for link-comparison purposes and would
// throw this depth count off by one).
function basePath(path) {
  const depth = path === "/" ? 0 : path.replace(/^\//, "").split("/").length - 1;
  return depth > 0 ? "../".repeat(depth) : "";
}

export function renderHeader(currentPath) {
  const current = normPath(currentPath);
  const base = basePath(currentPath);
  const isServicesGroup = SERVICES.some((s) => s.href === current) || current === "services";
  const isIndustriesGroup = INDUSTRIES.some((s) => s.href === current) || current === "industries";

  const desktopLinks = NAV_LINKS.map((link) => {
    const groupActive = link.label === "Services" ? isServicesGroup : link.label === "Industries" ? isIndustriesGroup : false;
    const active = link.href === current || (link.children && groupActive);
    if (link.children) {
      const overviewLabel = link.label === "Industries" ? "Industries Overview" : "Services Overview";
      return `<details class="nav-dropdown">
        <summary class="${active ? "is-active" : ""}">${link.label}<svg class="nav-dropdown__chevron" viewBox="0 0 12 8" width="10" height="7" aria-hidden="true"><path d="M1 1l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></summary>
        <div class="nav-dropdown__panel">
          <a href="${base}${link.href}">${overviewLabel}</a>
          ${link.children.map((c) => `<a href="${base}${c.href}" class="${c.href === current ? "is-active" : ""}">${c.label}</a>`).join("\n")}
        </div>
      </details>`;
    }
    return `<a href="${base}${link.href}" class="${active ? "is-active" : ""}">${link.label}</a>`;
  }).join("\n");

  const mobileLinks = NAV_LINKS.map((link) => {
    if (link.children) {
      const overviewLabel = link.label === "Industries" ? "Industries Overview" : "Services Overview";
      return `<details class="mobile-nav__dropdown">
        <summary>${link.label}</summary>
        <div class="mobile-nav__dropdown-panel">
          <a href="${base}${link.href}">${overviewLabel}</a>
          ${link.children.map((c) => `<a href="${base}${c.href}">${c.label}</a>`).join("\n")}
        </div>
      </details>`;
    }
    return `<a href="${base}${link.href}">${link.label}</a>`;
  }).join("\n");

  return `<header class="site-header">
  <div class="container site-header__inner">
    <a class="brand" href="${base || "./"}" aria-label="${SITE_NAME} home">
      ${brandGlyph(base)}
      <span class="brand__word">Water Buffalo <em>Media</em></span>
    </a>

    <nav class="nav" aria-label="Primary">
      ${desktopLinks}
    </nav>

    <a class="btn btn--primary btn--sm nav__cta" href="${base}contact">${CTA_LABEL}</a>

    <button class="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="mobile-nav">
      <span></span><span></span><span></span>
    </button>
  </div>

  <div class="mobile-nav" id="mobile-nav" hidden>
    ${mobileLinks}
    <a class="btn btn--primary" href="${base}contact">${CTA_LABEL}</a>
  </div>
</header>`;
}

function brandGlyph(base = "") {
  return `<img class="brand__glyph" src="${base}assets/logo-mark-icon.png" alt="" width="52" height="36" aria-hidden="true">`;
}

// ---------------------------------------------------------------
// Footer
// ---------------------------------------------------------------
export function renderFooter(currentPath = "/") {
  const base = basePath(currentPath);
  return `<footer class="site-footer">
  <div class="container footer__top">
    <div class="footer__brand">
      <a class="brand" href="${base || "./"}">
        ${brandGlyph(base)}
        <span class="brand__word">Water Buffalo <em>Media</em></span>
      </a>
      <h2 class="footer__headline">Built for Lasting Visibility.</h2>
      <p>Water Buffalo Media helps businesses build durable visibility across Google Search, Google Maps, and emerging AI search platforms. Our work is grounded in strong technical foundations, thoughtful strategy, and steady long-term progress.</p>
      <a class="footer__email" href="mailto:contact@waterbuffalomedia.com">contact@waterbuffalomedia.com</a>
      <a class="btn btn--primary" href="${base}contact">${CTA_LABEL}</a>
    </div>

    <nav class="footer__col" aria-label="Site">
      <h4>Site</h4>
      <a href="${base || "./"}">Home</a>
      <a href="${base}about">About</a>
      <a href="${base}services">Services</a>
      <a href="${base}contact">Contact</a>
      <a href="${base}privacy">Privacy Policy</a>
    </nav>

    <nav class="footer__col" aria-label="Services">
      <h4>Services</h4>
      <a href="${base}local-seo">Local SEO</a>
      <a href="${base}national-seo">National SEO</a>
      <a href="${base}global-seo">Global SEO</a>
      <a href="${base}ai-search">Generative Engine Optimization</a>
      <a href="${base}google-business-profile">Google Business Profile Optimization</a>
      <a href="${base}technical-seo">Technical SEO</a>
    </nav>

    <nav class="footer__col" aria-label="Industries">
      <h4>Industries</h4>
      <a href="${base}industries/hvac-marketing">HVAC</a>
      <a href="${base}industries/plumbing-marketing">Plumbing</a>
      <a href="${base}industries/electrical-contractor-marketing">Electrical</a>
      <a href="${base}industries/roofing-siding-marketing">Roofing & Siding</a>
      <a href="${base}industries/kitchen-remodeling-marketing">Kitchen Remodeling</a>
      <a href="${base}industries/landscaping-marketing">Landscaping</a>
      <a href="${base}industries">View All Industries</a>
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
export function renderHero({ eyebrow, headline, body, primaryLabel = CTA_LABEL, primaryHref = "contact", secondaryLabel, secondaryHref, showBuffalo = false, showLogoMark = false, logoMarkBase = "", compact = false, hideActions = false }) {
  const mark = showBuffalo
    ? `<img class="hero__buffalo" src="assets/buffalo-hero.png" alt="" aria-hidden="true" loading="eager" fetchpriority="high" width="798" height="884">`
    : showLogoMark
    ? `<img class="hero__buffalo hero__buffalo--logo" src="${logoMarkBase}assets/logo-mark.png" alt="" aria-hidden="true" loading="eager" width="640" height="437">`
    : "";
  return `<section class="hero${compact ? " hero--compact" : ""}">
    <div class="hero__glow" aria-hidden="true"></div>
    ${mark}
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
export function renderCta({ headline, body, primaryLabel = CTA_LABEL, primaryHref = "contact", secondaryLabel, secondaryHref }) {
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
// Industry card — reuses the exact .card/.service-card visual
// treatment (icon, heading, description, link) so the industries
// hub grid looks like a native part of the existing design system.
// ---------------------------------------------------------------
export function renderIndustryCard(industry) {
  return `<article class="card service-card reveal">
    <span class="card__icon" aria-hidden="true">${svgIcon(industry.icon || "search")}</span>
    <h3>${esc(industry.name)}</h3>
    <p>${esc(industry.description)}</p>
    <a class="service-card__link" href="${industry.href}">${esc(industry.title)} <span aria-hidden="true">&rarr;</span></a>
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

// A wrapping pill/tag grid — for long capability or category lists
// (10-20 items) a stacked checklist reads as a monotonous wall of
// checkmarks; tags scan faster and don't imply a literal to-do list.
export function renderTagGrid(items) {
  return `<div class="tag-grid">
    ${items.map((it) => `<span class="tag-grid__item">${esc(it)}</span>`).join("\n")}
  </div>`;
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
        : sec.tags
        ? renderTagGrid(sec.tags)
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
  const base = basePath(path);
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
${renderFooter(path)}
<script src="${base}js/main.js"></script>
</body>
</html>
`;
}
