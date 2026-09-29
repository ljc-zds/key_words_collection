import { chromium } from "playwright";
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs/promises";

const root = path.resolve(import.meta.dirname, "..");
const report = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, "outputs/keyword_site_analysis_20260911_local/关键词建站机会分析.html");
const canonicalPath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(root, "outputs/keyword_site_analysis_20260911_local/keyword_site_analysis.json");
const canonical = JSON.parse(await fs.readFile(canonicalPath, "utf8"));
const browser = await chromium.launch({ headless: true });

async function verify(viewport, screenshot) {
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", message => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(pathToFileURL(report).href);
  await page.waitForSelector("#keyword-table-body tr");

  const projectCount = await page.locator("#project-count").textContent();
  const keywordCount = await page.locator("#keyword-count").textContent();
  const expectedProjects = canonical.summary.project_count;
  const expectedKeywords = canonical.summary.accepted_keywords;
  if (!projectCount.includes(`${expectedProjects} / ${expectedProjects}`)) throw new Error(`Project count mismatch: ${projectCount}`);
  if (!keywordCount.includes(`${expectedKeywords} / ${expectedKeywords}`)) throw new Error(`Keyword count mismatch: ${keywordCount}`);

  await page.locator("#keyword-source").selectOption({ label: "Semrush" });
  const semrushCount = await page.locator("#keyword-count").textContent();
  const semrushOnly = canonical.summary.source_statuses.Semrush || 0;
  if (!semrushCount.includes(`${semrushOnly} / ${expectedKeywords}`)) throw new Error(`Source filter mismatch: ${semrushCount}`);
  await page.locator("#keyword-source").selectOption("");

  await page.locator("#project-search").fill("fantasy");
  const filteredProjects = await page.locator("#project-table-body tr").count();
  if (filteredProjects < 1) throw new Error("Project search returned no fantasy projects");
  await page.locator("#project-table-body .detail-btn").first().click();
  if (!(await page.locator("#detail-panel").getAttribute("class")).includes("open")) throw new Error("Detail panel did not open");
  await page.locator("#detail-close").click();
  await page.locator("#project-search").fill("");

  const firstKeywordPurpose = canonical.keywords[0].keyword_purpose;
  await page.locator("#keyword-table-body .detail-btn").first().click();
  const keywordDetail = await page.locator("#detail-content").textContent();
  if (!keywordDetail.includes("关键词用途说明") || !keywordDetail.includes(firstKeywordPurpose)) {
    throw new Error("Keyword purpose is missing from keyword detail");
  }
  await page.locator("#detail-close").click();

  const overflow = await page.evaluate(() => ({
    pageWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    offenders: [...document.querySelectorAll("body *")]
      .map(element => ({
        tag: element.tagName,
        id: element.id,
        className: String(element.className),
        right: Math.round(element.getBoundingClientRect().right),
        width: Math.round(element.getBoundingClientRect().width),
      }))
      .filter(item => item.right > window.innerWidth + 1)
      .slice(0, 8),
  }));
  if (overflow.pageWidth > overflow.viewportWidth + 1) throw new Error(`Page overflows viewport at ${viewport.width}px: ${JSON.stringify(overflow)}`);
  if (errors.length) throw new Error(`Browser errors: ${errors.join(" | ")}`);
  await page.screenshot({ path: screenshot, fullPage: true });
  await page.close();
}

try {
  await verify({ width: 1440, height: 1000 }, "/private/tmp/keyword-site-html-desktop.png");
  console.log("HTML browser verification passed at 1440px");
} finally {
  await browser.close();
}
