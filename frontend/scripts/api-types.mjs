import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import openapiTS, { astToString } from "openapi-typescript";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const python =
  process.env.PYTHON ||
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const schemaPath = path.join(root, ".artifacts/openapi.json");
mkdirSync(path.dirname(schemaPath), { recursive: true });
const result = spawnSync(
  python,
  ["-m", "lost_property.cli", "export-openapi", "--output", schemaPath],
  { cwd: path.join(root, "backend"), encoding: "utf8" },
);
if (result.status !== 0)
  throw new Error(
    result.stderr || "Unable to export the backend OpenAPI contract.",
  );
const output = astToString(
  await openapiTS(JSON.parse(readFileSync(schemaPath, "utf8"))),
);
const destination = path.join(root, "frontend/src/api/schema.d.ts");
mkdirSync(path.dirname(destination), { recursive: true });
if (process.argv.includes("--check")) {
  if (readFileSync(destination, "utf8") !== output)
    throw new Error("API types have drifted. Run npm run api:generate.");
  console.log("Generated API types match the backend contract.");
} else {
  writeFileSync(destination, output);
  console.log("Generated public API types.");
}
