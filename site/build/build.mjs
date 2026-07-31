import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { renderPage, SITE_URL, publicUrlPath } from "./components.mjs";

import * as home from "./pages/home.mjs";
import * as services from "./pages/services.mjs";
import * as localSeo from "./pages/local-seo.mjs";
import * as nationalSeo from "./pages/national-seo.mjs";
import * as globalSeo from "./pages/global-seo.mjs";
import * as aiSearch from "./pages/ai-search.mjs";
import * as gbp from "./pages/google-business-profile.mjs";
import * as technicalSeo from "./pages/technical-seo.mjs";
import * as about from "./pages/about.mjs";
import * as contact from "./pages/contact.mjs";
import * as privacy from "./pages/privacy.mjs";
import * as notFound from "./pages/404.mjs";

import * as industries from "./pages/industries.mjs";
import * as hvac from "./pages/industries/hvac-marketing.mjs";
import * as pestControl from "./pages/industries/pest-control-marketing.mjs";
import * as bathroomRemodeling from "./pages/industries/bathroom-remodeling-marketing.mjs";
import * as roofingSiding from "./pages/industries/roofing-siding-marketing.mjs";
import * as windowInstallation from "./pages/industries/window-installation-marketing.mjs";
import * as plumbing from "./pages/industries/plumbing-marketing.mjs";
import * as electrical from "./pages/industries/electrical-contractor-marketing.mjs";
import * as kitchenRemodeling from "./pages/industries/kitchen-remodeling-marketing.mjs";
import * as landscaping from "./pages/industries/landscaping-marketing.mjs";
import * as paintingContractor from "./pages/industries/painting-contractor-marketing.mjs";
import * as financialServices from "./pages/industries/financial-services-marketing.mjs";
import * as legalServices from "./pages/industries/legal-services-marketing.mjs";
import * as healthcareProvider from "./pages/industries/healthcare-provider-marketing.mjs";
import * as saasTechnology from "./pages/industries/saas-technology-marketing.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteRoot = join(__dirname, "..");

const pages = [
  home,
  services,
  localSeo,
  nationalSeo,
  globalSeo,
  aiSearch,
  gbp,
  technicalSeo,
  about,
  contact,
  privacy,
  industries,
  hvac,
  pestControl,
  bathroomRemodeling,
  roofingSiding,
  windowInstallation,
  plumbing,
  electrical,
  kitchenRemodeling,
  landscaping,
  paintingContractor,
  financialServices,
  legalServices,
  healthcareProvider,
  saasTechnology,
  notFound,
];

// industries/* pages are the first pages to sit one directory deep —
// the output folder needs to exist before we can write into it.
mkdirSync(join(siteRoot, "industries"), { recursive: true });

function outFileFor(path) {
  if (path === "/") return "index.html";
  return path.replace(/^\//, "");
}

// Inlined directly into every page's <head> (as a <style> block) rather than
// linked as an external stylesheet. This is a multi-page static site — every
// navigation is a full document load — so an external CSS request is one more
// round trip during which the page can paint unstyled (giant logo on a white
// background) before it resolves. Inlining removes that request entirely.
const cssContent = readFileSync(join(siteRoot, "css", "style.css"), "utf8");

for (const page of pages) {
  const html = renderPage({
    path: page.path,
    title: page.title,
    description: page.description,
    schemas: page.schemas || [],
    bodyHtml: page.bodyHtml,
    noindex: page.noindex || false,
    inlineCss: cssContent,
  });
  const outFile = join(siteRoot, outFileFor(page.path));
  writeFileSync(outFile, html);
  console.log("wrote", outFileFor(page.path));
}

// sitemap.xml (exclude 404)
const urls = pages
  .filter((p) => p.path !== "/404.html")
  .map((p) => `  <url><loc>${SITE_URL}${publicUrlPath(p.path)}</loc></url>`)
  .join("\n");
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
writeFileSync(join(siteRoot, "sitemap.xml"), sitemap);
console.log("wrote sitemap.xml");

const robots = `User-agent: *\nAllow: /\n\nSitemap: ${SITE_URL}/sitemap.xml\n`;
writeFileSync(join(siteRoot, "robots.txt"), robots);
console.log("wrote robots.txt");

console.log(`\nBuilt ${pages.length} pages.`);
