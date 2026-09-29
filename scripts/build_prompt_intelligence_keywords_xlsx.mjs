import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourcePath = path.resolve(
  "outputs/prompt_intelligence_20260924/prompt_intelligence_keywords.json",
);
const outputDir = path.resolve("outputs/prompt_intelligence_20260924_excel");
const outputPath = path.join(outputDir, "prompt_intelligence_keywords.xlsx");
const previewDir = "/private/tmp/prompt-intelligence-keywords-previews";

const raw = JSON.parse(await fs.readFile(sourcePath, "utf8"));
const records = raw.records ?? [];
const runs = raw.runs ?? [];

const nullableNumber = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const nullableText = (value) => {
  if (value === null || value === undefined) return "";
  return String(value);
};

const grouped = new Map();
for (const record of records) {
  const keyword = nullableText(record.keyword).trim();
  if (!keyword) continue;

  let item = grouped.get(keyword);
  if (!item) {
    item = {
      keyword,
      clusters: new Set(),
      providers: new Set(),
      recordCount: 0,
      similarweb: null,
      semrush: null,
      similarwebSeeds: new Set(),
      semrushSeeds: new Set(),
    };
    grouped.set(keyword, item);
  }

  item.recordCount += 1;
  if (record.cluster) item.clusters.add(String(record.cluster));
  if (record.provider) item.providers.add(String(record.provider));

  const provider = String(record.provider ?? "").toLowerCase();
  if (provider !== "similarweb" && provider !== "semrush") continue;

  const current = item[provider];
  const candidate = {
    volume: nullableNumber(record.volume),
    kd: nullableNumber(record.kd),
    cpc: nullableNumber(record.cpc),
    intent: nullableText(record.intent),
  };
  const currentVolume = current?.volume ?? -1;
  const candidateVolume = candidate.volume ?? -1;
  if (!current || candidateVolume > currentVolume) item[provider] = candidate;

  const seed = nullableText(record.seed).trim();
  if (seed) item[`${provider}Seeds`].add(seed);
}

const summaryRows = [...grouped.values()]
  .map((item) => [
    item.keyword,
    [...item.clusters].join("；"),
    item.similarweb?.volume ?? null,
    item.similarweb?.kd ?? null,
    item.similarweb?.cpc ?? null,
    item.similarweb?.intent ?? "",
    [...item.similarwebSeeds].sort().join("；"),
    item.semrush?.volume ?? null,
    item.semrush?.kd ?? null,
    item.semrush?.cpc ?? null,
    item.semrush?.intent ?? "",
    [...item.semrushSeeds].sort().join("；"),
    item.providers.size,
    item.recordCount,
  ])
  .sort((a, b) => {
    const aVolume = Math.max(a[2] ?? -1, a[7] ?? -1);
    const bVolume = Math.max(b[2] ?? -1, b[7] ?? -1);
    return bVolume - aVolume || String(a[0]).localeCompare(String(b[0]));
  });

const rawRows = records.map((record) => [
  nullableText(record.keyword),
  nullableText(record.cluster),
  nullableText(record.provider),
  nullableText(record.market),
  nullableText(record.seed),
  nullableNumber(record.volume),
  nullableNumber(record.kd),
  nullableNumber(record.cpc),
  nullableText(record.intent),
  nullableText(record.leading_site),
]);

const runRows = runs
  .map((run) => [
    nullableText(run.provider),
    nullableText(run.seed),
    nullableNumber(run.row_count),
    run.error ? "失败" : "正常",
    nullableText(run.error),
    run.collected_at ? new Date(run.collected_at) : null,
  ])
  .sort((a, b) => String(a[0]).localeCompare(String(b[0])) || String(a[1]).localeCompare(String(b[1])));

const workbook = Workbook.create();
const summary = workbook.worksheets.add("关键词汇总");
const allRecords = workbook.worksheets.add("全部记录");
const collectionRuns = workbook.worksheets.add("采集状态");
const definitions = workbook.worksheets.add("字段说明");

const fontFamily = "Arial";
const titleColor = "#17324D";
const accentColor = "#2D6A4F";
const lightAccent = "#EAF4EF";
const borderColor = "#D9E2E8";
const bodyColor = "#17212B";

function styleTitle(sheet, lastColumn, title, subtitle) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}1`).format.borders = {
    bottom: { style: "thin", color: borderColor },
  };
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format.font = {
    name: fontFamily,
    size: 16,
    bold: true,
    color: titleColor,
  };
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${lastColumn}2`).format.font = {
    name: fontFamily,
    size: 10,
    italic: true,
    color: "#52616B",
  };
  sheet.getRange(`A1:${lastColumn}2`).format.rowHeight = 24;
}

function styleHeader(range) {
  range.format = {
    fill: titleColor,
    font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: {
      insideVertical: { style: "thin", color: "#FFFFFF" },
      bottom: { style: "medium", color: titleColor },
    },
  };
  range.format.rowHeight = 34;
}

function writeInChunks(sheet, startRow, rows, columnCount, chunkSize = 1500) {
  for (let offset = 0; offset < rows.length; offset += chunkSize) {
    const chunk = rows.slice(offset, offset + chunkSize);
    sheet
      .getRangeByIndexes(startRow + offset, 0, chunk.length, columnCount)
      .writeValues(chunk);
  }
}

styleTitle(
  summary,
  "N",
  "Prompt Intelligence 关键词汇总",
  "Similarweb Global 与 Semrush US，本轮采集时间：2026-09-24；两平台指标分开保留，不进行相加。",
);
summary.getRange("A3:H3").values = [[
  "唯一关键词",
  summaryRows.length,
  "全部来源记录",
  records.length,
  "采集任务",
  runs.length,
  "数据来源",
  "Similarweb Global / Semrush US",
]];
summary.getRange("A3:H3").format = {
  fill: lightAccent,
  font: { name: fontFamily, size: 10, bold: true, color: bodyColor },
  verticalAlignment: "center",
};
summary.getRange("B3,D3,F3").format.numberFormat = "#,##0";
summary.getRange("A5:N5").values = [[
  "关键词",
  "关键词簇",
  "Similarweb 搜索量",
  "Similarweb KD",
  "Similarweb CPC",
  "Similarweb 意图",
  "Similarweb 采集词根",
  "Semrush 搜索量",
  "Semrush KD",
  "Semrush CPC",
  "Semrush 意图",
  "Semrush 采集词根",
  "覆盖平台数",
  "来源记录数",
]];
styleHeader(summary.getRange("A5:N5"));
writeInChunks(summary, 5, summaryRows, 14);
const summaryLastRow = 5 + summaryRows.length;
summary.tables.add(`A5:N${summaryLastRow}`, true, "KeywordSummaryTable").style = "TableStyleMedium2";
summary.freezePanes.freezeRows(5);
summary.freezePanes.freezeColumns(2);
summary.getRange(`A6:N${summaryLastRow}`).format.font = { name: fontFamily, size: 10, color: bodyColor };
summary.getRange(`C6:C${summaryLastRow}`).format.numberFormat = "#,##0";
summary.getRange(`D6:D${summaryLastRow}`).format.numberFormat = "0.0";
summary.getRange(`E6:E${summaryLastRow}`).format.numberFormat = "0.00";
summary.getRange(`H6:H${summaryLastRow}`).format.numberFormat = "#,##0";
summary.getRange(`I6:I${summaryLastRow}`).format.numberFormat = "0.0";
summary.getRange(`J6:J${summaryLastRow}`).format.numberFormat = "0.00";
summary.getRange(`M6:N${summaryLastRow}`).format.numberFormat = "#,##0";
summary.getRange("A:A").format.columnWidth = 40;
summary.getRange("B:B").format.columnWidth = 24;
summary.getRange("C:E").format.columnWidth = 15;
summary.getRange("F:F").format.columnWidth = 22;
summary.getRange("G:G").format.columnWidth = 30;
summary.getRange("H:J").format.columnWidth = 15;
summary.getRange("K:K").format.columnWidth = 22;
summary.getRange("L:L").format.columnWidth = 30;
summary.getRange("M:N").format.columnWidth = 13;

styleTitle(
  allRecords,
  "J",
  "Prompt Intelligence 全部采集记录",
  "保留每条记录的数据源、市场和采集词根；同一关键词可能因多个词根或平台重复出现。",
);
allRecords.getRange("A5:J5").values = [[
  "关键词",
  "关键词簇",
  "数据源",
  "市场",
  "采集词根",
  "搜索量",
  "KD",
  "CPC",
  "意图",
  "领先站点",
]];
styleHeader(allRecords.getRange("A5:J5"));
writeInChunks(allRecords, 5, rawRows, 10);
const rawLastRow = 5 + rawRows.length;
allRecords.tables.add(`A5:J${rawLastRow}`, true, "AllKeywordRecordsTable").style = "TableStyleMedium2";
allRecords.freezePanes.freezeRows(5);
allRecords.freezePanes.freezeColumns(2);
allRecords.getRange(`A6:J${rawLastRow}`).format.font = { name: fontFamily, size: 10, color: bodyColor };
allRecords.getRange(`F6:F${rawLastRow}`).format.numberFormat = "#,##0";
allRecords.getRange(`G6:G${rawLastRow}`).format.numberFormat = "0.0";
allRecords.getRange(`H6:H${rawLastRow}`).format.numberFormat = "0.00";
allRecords.getRange("A:A").format.columnWidth = 48;
allRecords.getRange("B:B").format.columnWidth = 24;
allRecords.getRange("C:D").format.columnWidth = 14;
allRecords.getRange("E:E").format.columnWidth = 24;
allRecords.getRange("F:H").format.columnWidth = 13;
allRecords.getRange("I:I").format.columnWidth = 24;
allRecords.getRange("J:J").format.columnWidth = 32;

styleTitle(
  collectionRuns,
  "F",
  "采集任务状态",
  "本轮共执行 20 个平台与词根任务；返回记录为各任务写入的数据行数。",
);
collectionRuns.getRange("A5:F5").values = [[
  "数据源",
  "词根",
  "返回记录",
  "状态",
  "错误信息",
  "采集时间",
]];
styleHeader(collectionRuns.getRange("A5:F5"));
writeInChunks(collectionRuns, 5, runRows, 6);
const runLastRow = 5 + runRows.length;
collectionRuns.tables.add(`A5:F${runLastRow}`, true, "CollectionRunsTable").style = "TableStyleMedium2";
collectionRuns.freezePanes.freezeRows(5);
collectionRuns.getRange(`A6:F${runLastRow}`).format.font = { name: fontFamily, size: 10, color: bodyColor };
collectionRuns.getRange(`C6:C${runLastRow}`).format.numberFormat = "#,##0";
collectionRuns.getRange(`F6:F${runLastRow}`).format.numberFormat = "yyyy-mm-dd hh:mm:ss";
collectionRuns.getRange(`D6:D${runLastRow}`).conditionalFormats.add("containsText", {
  text: "正常",
  format: { fill: "#E7F4E4", font: { color: "#1B5E20", bold: true } },
});
collectionRuns.getRange(`D6:D${runLastRow}`).conditionalFormats.add("containsText", {
  text: "失败",
  format: { fill: "#FCE8E6", font: { color: "#B3261E", bold: true } },
});
collectionRuns.getRange("A:A").format.columnWidth = 16;
collectionRuns.getRange("B:B").format.columnWidth = 28;
collectionRuns.getRange("C:D").format.columnWidth = 14;
collectionRuns.getRange("E:E").format.columnWidth = 38;
collectionRuns.getRange("F:F").format.columnWidth = 22;

styleTitle(
  definitions,
  "D",
  "字段说明与数据来源",
  "指标口径以采集平台返回结果为准。Similarweb 与 Semrush 的市场和估算方法不同，不应直接相加。",
);
definitions.getRange("A5:D5").values = [["字段", "说明", "适用工作表", "备注"]];
styleHeader(definitions.getRange("A5:D5"));
const definitionRows = [
  ["关键词", "平台返回的关键词文本。", "关键词汇总、全部记录", "跨平台汇总以完整关键词文本去重。"],
  ["关键词簇", "本轮规则分配的主题类别。", "关键词汇总、全部记录", "用于浏览，不代表最终建站决策。"],
  ["数据源", "Similarweb 或 Semrush。", "全部记录、采集状态", "Similarweb 市场为 Global；Semrush 市场为 US。"],
  ["采集词根", "触发该记录的起始关键词。", "关键词汇总、全部记录", "同一关键词可以由多个词根发现。"],
  ["搜索量", "平台返回的月度搜索量估算。", "关键词汇总、全部记录", "不同平台数据不可相加。"],
  ["KD", "平台返回的关键词难度。", "关键词汇总、全部记录", "空白表示平台未返回。"],
  ["CPC", "平台返回的单次点击成本估算。", "关键词汇总、全部记录", "空白表示平台未返回。"],
  ["意图", "平台返回或规则识别的搜索意图。", "关键词汇总、全部记录", "可能为空。"],
  ["覆盖平台数", "该关键词出现的平台数量。", "关键词汇总", "取值范围为 1 至 2。"],
  ["来源记录数", "该关键词在全部记录中的行数。", "关键词汇总", "包含不同平台和不同采集词根。"],
  ["来源网址", "Similarweb", "数据来源", "https://www.similarweb.com/"],
  ["来源网址", "Semrush", "数据来源", "https://www.semrush.com/"],
];
writeInChunks(definitions, 5, definitionRows, 4);
const definitionLastRow = 5 + definitionRows.length;
definitions.tables.add(`A5:D${definitionLastRow}`, true, "FieldDefinitionsTable").style = "TableStyleMedium2";
definitions.freezePanes.freezeRows(5);
definitions.getRange(`A6:D${definitionLastRow}`).format = {
  font: { name: fontFamily, size: 10, color: bodyColor },
  verticalAlignment: "top",
  wrapText: true,
};
definitions.getRange("A:A").format.columnWidth = 18;
definitions.getRange("B:B").format.columnWidth = 42;
definitions.getRange("C:C").format.columnWidth = 26;
definitions.getRange("D:D").format.columnWidth = 50;
definitions.getRange(`A6:D${definitionLastRow}`).format.autofitRows();

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const summaryInspect = await workbook.inspect({
  kind: "table",
  range: "关键词汇总!A1:N18",
  include: "values,formulas",
  tableMaxRows: 18,
  tableMaxCols: 14,
});
console.log("SUMMARY_INSPECT");
console.log(summaryInspect.ndjson);

const errorInspect = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log("ERROR_SCAN");
console.log(errorInspect.ndjson);

for (const [sheetName, range] of [
  ["关键词汇总", "A1:N22"],
  ["全部记录", "A1:J22"],
  ["采集状态", "A1:F25"],
  ["字段说明", "A1:D17"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const filename = `${sheetName}.png`;
  await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(JSON.stringify({
  outputPath,
  previewDir,
  recordCount: records.length,
  uniqueKeywordCount: summaryRows.length,
  runCount: runs.length,
}));
