import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputPath] = process.argv.slice(2);
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();
const summary = workbook.worksheets.add("판별결과");
const raw = workbook.worksheets.add("OCR_Qwen");

summary.getRange("A1:C1").merge();
summary.getRange("A1").values = [["적격성 검토 통합 결과"]];
summary.getRange("A2:B5").values = [
  ["연구책임자명", data.input_researcher || ""],
  ["주관기관명", data.input_organization || ""],
  ["완료 항목", `${data.completed || 0} / ${data.total || 0}`],
  ["총 소요시간(초)", Number(data.elapsed_seconds || 0)],
];
summary.getRange("A7:C7").values = [["검토 항목", "판별 결과", "점수"]];
const rows = (data.rows || []).map((row) => [row.item || "", row.status || "", Number(row.score || 0)]);
if (rows.length) summary.getRange(`A8:C${rows.length + 7}`).values = rows;
const totalRow = rows.length + 9;
summary.getRange(`A${totalRow}:B${totalRow}`).values = [["최종 점수 합계", ""]];
summary.getRange(`C${totalRow}`).formulas = [[`=SUM(C8:C${rows.length + 7})`]];
summary.getRange("A1:C1").format = { fill: "#253B80", font: { bold: true, color: "#FFFFFF", size: 14 }, horizontalAlignment: "center" };
summary.getRange("A7:C7").format = { fill: "#DCE5FF", font: { bold: true, color: "#1F2A5A" }, borders: { preset: "all", style: "thin", color: "#B8C2DF" } };
summary.getRange(`A8:C${totalRow}`).format = { borders: { preset: "all", style: "thin", color: "#D9DDEB" } };
summary.getRange(`C8:C${totalRow}`).format.numberFormat = "0.0";
summary.getRange("A1:C1").format.rowHeight = 28;
summary.getRange("A:A").format.columnWidth = 30;
summary.getRange("B:B").format.columnWidth = 24;
summary.getRange("C:C").format.columnWidth = 12;
summary.freezePanes.freezeRows(7);

raw.getRange("A1:B1").values = [["파일명", "OCR 원문"]];
const ocrRows = (data.ocr_results || []).map((item) => [item.name || "", item.text || ""]);
if (ocrRows.length) raw.getRange(`A2:B${ocrRows.length + 1}`).values = ocrRows;
const qwenStart = ocrRows.length + 4;
raw.getRange(`A${qwenStart}:B${qwenStart}`).values = [["Qwen JSON", JSON.stringify(data.qwen_result || {}, null, 2)]];
raw.getRange("A1:B1").format = { fill: "#253B80", font: { bold: true, color: "#FFFFFF" } };
raw.getRange(`A1:B${qwenStart}`).format = { wrapText: true, borders: { preset: "all", style: "thin", color: "#D9DDEB" } };
raw.getRange("A:A").format.columnWidth = 34;
raw.getRange("B:B").format.columnWidth = 100;
raw.getRange(`B2:B${qwenStart}`).format.wrapText = true;
raw.freezePanes.freezeRows(1);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
