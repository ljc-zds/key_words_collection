import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const defaultOutDir = path.join(root, "outputs", "keyword_site_analysis_20260911_local");
const inputPath = process.argv[2] ? path.resolve(process.argv[2]) : path.join(defaultOutDir, "keyword_site_analysis.json");
const outputPath = process.argv[3] ? path.resolve(process.argv[3]) : path.join(defaultOutDir, "关键词建站机会.xlsx");
const outDir = path.dirname(outputPath);
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));

const workbook = Workbook.create();
const projectsSheet = workbook.worksheets.add("建站项目排名");
const keywordsSheet = workbook.worksheets.add("关键词明细");
const methodSheet = workbook.worksheets.add("评分口径");

const navy = "#19324A";
const charcoal = "#24313D";
const paleBlue = "#EAF2F8";
const paleGreen = "#E8F3EC";
const paleAmber = "#FFF3D6";
const paleRed = "#FBE9E7";
const line = "#D5DDE5";
const muted = "#5F6B76";

function writeTitle(sheet, title, subtitle, lastColumn) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}1`).format.borders = { bottom: { style: "thin", color: navy } };
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format.font = { name: "Arial", size: 16, bold: true, color: charcoal };
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${lastColumn}2`).format.font = { name: "Arial", size: 10, italic: true, color: muted };
}

function styleTable(sheet, range, headerRange) {
  range.format.font = { name: "Arial", size: 10, color: charcoal };
  range.format.verticalAlignment = "center";
  headerRange.format.fill = navy;
  headerRange.format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
  headerRange.format.horizontalAlignment = "center";
  headerRange.format.wrapText = true;
  headerRange.format.rowHeightPx = 36;
}

const projectHeaders = [
  "排名", "优先级", "项目得分", "项目名称", "主关键词", "站点类型", "关键词数",
  "主词搜索量", "保守KD", "变现方式", "风险说明", "推荐理由", "SERP验证",
];
const projectRows = data.projects.map((item) => [
  item.rank, item.priority, item.score, item.project_name, item.main_keyword, item.site_type,
  item.keyword_count, item.main_volume, item.main_kd, item.monetization, item.risk_notes,
  item.reason, "未进行实时 SERP 验证",
]);
writeTitle(
  projectsSheet,
  "建站项目排名",
  `本地数据分析｜Similarweb Global + Semrush US｜${data.summary.accepted_keywords} 个合格关键词聚合为 ${data.summary.project_count} 个项目`,
  "M",
);
projectsSheet.getRange("A4:M4").values = [projectHeaders];
if (projectRows.length) projectsSheet.getRange("A5").write(projectRows);
const projectEnd = 4 + projectRows.length;
const projectRange = projectsSheet.getRange(`A4:M${projectEnd}`);
styleTable(projectsSheet, projectRange, projectsSheet.getRange("A4:M4"));
const projectTable = projectsSheet.tables.add(`A4:M${projectEnd}`, true, "SiteProjectsTable");
projectTable.style = "TableStyleMedium2";
projectTable.showBandedColumns = false;
projectsSheet.freezePanes.freezeRows(4);
projectsSheet.getRange(`A5:C${projectEnd}`).format.horizontalAlignment = "center";
projectsSheet.getRange(`G5:I${projectEnd}`).format.horizontalAlignment = "right";
projectsSheet.getRange(`C5:C${projectEnd}`).setNumberFormat("0.0");
projectsSheet.getRange(`G5:I${projectEnd}`).setNumberFormat("#,##0");
projectsSheet.getRange(`J5:M${projectEnd}`).format.wrapText = true;
projectsSheet.getRange(`B5:B${projectEnd}`).conditionalFormats.add("containsText", { text: "P0", format: { fill: paleGreen, font: { bold: true, color: "#17613A" } } });
projectsSheet.getRange(`B5:B${projectEnd}`).conditionalFormats.add("containsText", { text: "P1", format: { fill: paleAmber, font: { bold: true, color: "#785800" } } });
projectsSheet.getRange(`B5:B${projectEnd}`).conditionalFormats.add("containsText", { text: "P2", format: { fill: paleBlue, font: { bold: true, color: "#234F78" } } });
const projectWidths = [8, 10, 12, 30, 30, 20, 10, 15, 10, 28, 34, 44, 24];
projectWidths.forEach((width, index) => { projectsSheet.getRangeByIndexes(0, index, projectEnd, 1).format.columnWidth = width; });

const keywordHeaders = [
  "排名", "项目排名", "优先级", "综合得分", "关键词", "关键词用途说明", "项目名称", "站点类型", "来源状态",
  "需求搜索量", "保守KD", "Similarweb搜索量", "Similarweb KD", "Similarweb Intent", "Similarweb根词",
  "Semrush搜索量", "Semrush KD", "Semrush CPC", "Semrush Intent", "Semrush父词", "需求得分",
  "SEO得分", "产品得分", "变现得分", "扩展得分", "数据可信度", "风险扣分", "变现方式",
  "入选理由", "风险说明", "SERP验证",
];
const keywordRows = data.keywords.map((item) => [
  item.rank, item.project_rank, item.priority, item.score, item.keyword, item.keyword_purpose || "",
  item.project_name,
  item.site_type, item.source_status, item.demand_volume, item.conservative_kd,
  item.similarweb_volume ?? null, item.similarweb_kd ?? null, item.similarweb_intent ?? "",
  (item.similarweb_roots || []).join("、"), item.semrush_volume ?? null, item.semrush_kd ?? null,
  item.semrush_cpc ?? null, item.semrush_intent ?? "", (item.semrush_parents || []).join("、"),
  item.demand_score, item.seo_score, item.product_score, item.monetization_score,
  item.expansion_score, item.data_confidence_score, item.risk_penalty, item.monetization,
  item.decision_reason, item.risk_notes, item.serp_status,
]);
writeTitle(
  keywordsSheet,
  "合格关键词明细",
  "仅包含综合得分不低于 60 且通过硬性风险筛选的关键词；两个平台的指标保持独立",
  "AE",
);
keywordsSheet.getRange("A4:AE4").values = [keywordHeaders];
if (keywordRows.length) keywordsSheet.getRange("A5").write(keywordRows);
const keywordEnd = 4 + keywordRows.length;
const keywordRange = keywordsSheet.getRange(`A4:AE${keywordEnd}`);
styleTable(keywordsSheet, keywordRange, keywordsSheet.getRange("A4:AE4"));
const keywordTable = keywordsSheet.tables.add(`A4:AE${keywordEnd}`, true, "QualifiedKeywordsTable");
keywordTable.style = "TableStyleMedium2";
keywordsSheet.freezePanes.freezeRows(4);
keywordsSheet.freezePanes.freezeColumns(5);
keywordsSheet.getRange(`A5:D${keywordEnd}`).format.horizontalAlignment = "center";
keywordsSheet.getRange(`J5:M${keywordEnd}`).setNumberFormat("#,##0");
keywordsSheet.getRange(`P5:R${keywordEnd}`).setNumberFormat("#,##0.00");
keywordsSheet.getRange(`U5:AA${keywordEnd}`).setNumberFormat("0.0");
keywordsSheet.getRange(`F5:F${keywordEnd}`).format.wrapText = true;
keywordsSheet.getRange(`AB5:AE${keywordEnd}`).format.wrapText = true;
keywordsSheet.getRange(`C5:C${keywordEnd}`).conditionalFormats.add("containsText", { text: "P0", format: { fill: paleGreen, font: { bold: true, color: "#17613A" } } });
keywordsSheet.getRange(`C5:C${keywordEnd}`).conditionalFormats.add("containsText", { text: "P1", format: { fill: paleAmber, font: { bold: true, color: "#785800" } } });
keywordsSheet.getRange(`C5:C${keywordEnd}`).conditionalFormats.add("containsText", { text: "P2", format: { fill: paleBlue, font: { bold: true, color: "#234F78" } } });
const keywordWidths = [8, 10, 10, 11, 31, 58, 30, 19, 13, 14, 10, 17, 13, 20, 28, 15, 12, 13, 22, 28, 10, 10, 10, 10, 10, 12, 10, 28, 44, 38, 24];
keywordWidths.forEach((width, index) => { keywordsSheet.getRangeByIndexes(0, index, keywordEnd, 1).format.columnWidth = width; });

writeTitle(
  methodSheet,
  "评分口径与数据说明",
  `分析生成时间：${data.metadata.analysis_generated_at}｜数据最新时间：${data.metadata.latest_source_retrieved_at || "未知"}`,
  "H",
);
methodSheet.getRange("A4:B4").values = [["指标", "值"]];
methodSheet.getRange("A5:A11").values = [
  ["原始唯一关键词"], ["合格关键词"], ["建站项目"], ["P0"], ["P1"], ["P2"], ["SERP接口调用"],
];
methodSheet.getRange("B5").values = [[data.summary.raw_unique_keywords]];
methodSheet.getRange("B6").formulas = [[`=COUNTA('关键词明细'!$E$5:$E$${keywordEnd})`]];
methodSheet.getRange("B7").formulas = [[`=COUNTA('建站项目排名'!$D$5:$D$${projectEnd})`]];
methodSheet.getRange("B8").formulas = [[`=COUNTIF('关键词明细'!$C$5:$C$${keywordEnd},"P0")`]];
methodSheet.getRange("B9").formulas = [[`=COUNTIF('关键词明细'!$C$5:$C$${keywordEnd},"P1")`]];
methodSheet.getRange("B10").formulas = [[`=COUNTIF('关键词明细'!$C$5:$C$${keywordEnd},"P2")`]];
methodSheet.getRange("B11").values = [["未调用"]];
styleTable(methodSheet, methodSheet.getRange("A4:B11"), methodSheet.getRange("A4:B4"));
methodSheet.getRange("B5:B10").setNumberFormat("#,##0");

methodSheet.getRange("D4:H4").values = [["评分维度", "满分", "核心口径", "硬性门槛", "说明"]];
methodSheet.getRange("D5:H10").values = [
  ["搜索需求", 20, "可用平台中的最高搜索量分档", "搜索量 ≥ 5,000", "平台口径不同，原值不相加"],
  ["SEO可进入性", 25, "双来源时采用较高 KD", "KD ≤ 60", "保守处理平台差异"],
  ["产品化程度", 20, "工具、资源、比较或可扩展内容需求", "必须识别站点形态", "优先可直接交付结果的工具"],
  ["变现能力", 15, "CPC、商业/交易意图与站点类型", "无", "CPC缺失不会自动淘汰"],
  ["扩展能力", 10, "是否能形成长尾页面或功能集群", "无", "项目聚类不等于流量相加"],
  ["数据可信度", 10, "双来源最高，单来源降权", "指标完整", "不进行实时 SERP 验证"],
];
styleTable(methodSheet, methodSheet.getRange("D4:H10"), methodSheet.getRange("D4:H4"));
methodSheet.getRange("D12:E12").values = [["淘汰原因分类", "数量"]];
const exclusionRows = Object.entries(data.summary.exclusion_counts).map(([key, value]) => [key, value]);
methodSheet.getRange("D13").write(exclusionRows);
const exclusionEnd = 12 + exclusionRows.length;
styleTable(methodSheet, methodSheet.getRange(`D12:E${exclusionEnd}`), methodSheet.getRange("D12:E12"));
methodSheet.getRange(`E13:E${exclusionEnd}`).setNumberFormat("#,##0");
methodSheet.getRange("A13:C17").values = [
  ["优先级", "分数", "使用建议"],
  ["P0", "80–100", "本地数据最强，优先进入人工商业验证"],
  ["P1", "70–79.9", "具备明确机会，适合排入第二验证批次"],
  ["P2", "60–69.9", "可建站但数据或商业确定性较弱，作为储备"],
  ["限制", null, "本报告未调用 Google SERP、Semrush 或 Similarweb 在线接口；竞争结论仅来自本地数据"],
];
methodSheet.getRange("A13:C13").format.fill = navy;
methodSheet.getRange("A13:C13").format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
methodSheet.getRange("A14:C17").format.font = { name: "Arial", size: 10, color: charcoal };
methodSheet.getRange("A14:C17").format.wrapText = true;
methodSheet.getRange("A14:C17").format.borders = { bottom: { style: "thin", color: line } };
methodSheet.getRange("A14:A14").format.fill = paleGreen;
methodSheet.getRange("A15:A15").format.fill = paleAmber;
methodSheet.getRange("A16:A16").format.fill = paleBlue;
methodSheet.getRange("A17:C17").format.fill = paleRed;
methodSheet.freezePanes.freezeRows(4);
const methodWidths = [20, 16, 50, 24, 14, 34, 20, 34];
methodWidths.forEach((width, index) => { methodSheet.getRangeByIndexes(0, index, Math.max(exclusionEnd, 17), 1).format.columnWidth = width; });

await fs.mkdir(outDir, { recursive: true });
const keyInspect = await workbook.inspect({
  kind: "table",
  range: "评分口径!A4:H17",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
  maxChars: 9000,
});
const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
const previewRanges = {
  "建站项目排名": `A1:M${Math.min(projectEnd, 40)}`,
  "关键词明细": `A1:AE${Math.min(keywordEnd, 40)}`,
  "评分口径": `A1:H${Math.max(exclusionEnd, 17)}`,
};
for (const sheetName of ["建站项目排名", "关键词明细", "评分口径"]) {
  const preview = await workbook.render({ sheetName, range: previewRanges[sheetName], scale: 1, format: "png" });
  await fs.writeFile(path.join("/private/tmp", `keyword-site-${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, projectRows: projectRows.length, keywordRows: keywordRows.length, keyInspect: keyInspect.ndjson, formulaErrors: formulaErrors.ndjson }));
