import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourcePath = "C:/Users/ddelw/.codex/attachments/925cef5a-0d67-4b65-8344-c58e2fcc341f/pasted-text.txt";
const outputDir = "outputs/019fa90c-ed1f-7da3-ac7c-b5da1f4cd613";
const outputPath = `${outputDir}/crop_ids_and_names.xlsx`;
const previewPath = `${outputDir}/crop_ids_and_names_preview.png`;

const html = await fs.readFile(sourcePath, "utf8");
const rows = [];
const optionPattern = /<option\b[^>]*\bvalue="([^"]*)"[^>]*>([\s\S]*?)<\/option>/gi;
for (const match of html.matchAll(optionPattern)) {
  const id = match[1].trim();
  if (!id) continue;
  const cropName = match[2]
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&#39;/gi, "'")
    .replace(/&quot;/gi, '"')
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
  rows.push([id, cropName]);
}

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Crops");
sheet.showGridLines = false;
sheet.getRange("A1:B1").values = [["Crop ID", "Crop Name"]];
sheet.getRange(`A2:B${rows.length + 1}`).values = rows;

sheet.getRange("A1:B1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF", size: 11 },
  verticalAlignment: "center",
};
sheet.getRange("A1:B1").format.rowHeight = 24;
sheet.getRange(`A2:A${rows.length + 1}`).format.numberFormat = "@";
sheet.getRange(`A1:B${rows.length + 1}`).format.borders = {
  insideHorizontal: { style: "thin", color: "#D9E2F3" },
  bottom: { style: "thin", color: "#A6A6A6" },
};
sheet.getRange(`A2:B${rows.length + 1}`).format.verticalAlignment = "center";
sheet.getRange(`A2:B${rows.length + 1}`).format.rowHeight = 20;
sheet.getRange("A:A").format.columnWidth = 18;
sheet.getRange("B:B").format.columnWidth = 58;
sheet.freezePanes.freezeRows(1);
sheet.tables.add(`A1:B${rows.length + 1}`, true, "CropsTable");

const check = await workbook.inspect({
  kind: "table",
  range: `Crops!A1:B${Math.min(rows.length + 1, 12)}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 2,
});
console.log(check.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({
  sheetName: "Crops",
  range: `A1:B${Math.min(rows.length + 1, 25)}`,
  scale: 1.5,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewPath, rowCount: rows.length }));
