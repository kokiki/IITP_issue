import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load("integrated_review.xlsx"));
const summary = await workbook.inspect({
  kind: "table",
  sheetId: "판별결과",
  range: "A1:C16",
  include: "values,formulas",
  tableMaxRows: 16,
  tableMaxCols: 3,
});
console.log(summary.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
});
console.log("FORMULA_ERRORS", errors.ndjson || "none");
const preview = await workbook.render({ sheetName: "판별결과", range: "A1:C16", scale: 1, format: "png" });
await fs.writeFile("integrated_review_preview.png", new Uint8Array(await preview.arrayBuffer()));
