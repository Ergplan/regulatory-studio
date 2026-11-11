// Copy published order PDFs from the snapshot into public/pdf so Vercel serves them.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const snapshot = resolve(process.env.SNAPSHOT_DIR ?? "../data/snapshot");
const src = resolve(snapshot, "pdf");
const dest = resolve("public/pdf");
mkdirSync(dest, { recursive: true });
if (existsSync(src)) cpSync(src, dest, { recursive: true });
console.log(`pdfs: ${src} -> ${dest}`);
