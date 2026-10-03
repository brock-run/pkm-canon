// Dependency-free checks for the repo-owned architecture diagrams and map.
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const directory = path.join(root, "docs", "architecture");
const files = ["current-state.md", "target-state.md", "component-map.md"];
const errors = [];
const diagrams = new Map();
const markdown = new Map();

for (const name of files) {
  const file = path.join(directory, name);
  if (!fs.existsSync(file)) {
    errors.push(`Missing ${path.relative(root, file)}`);
    continue;
  }
  const content = fs.readFileSync(file, "utf8");
  markdown.set(name, content);
  for (const match of content.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)) {
    const target = match[2].split(/[?#]/, 1)[0];
    if (!target || /^(?:https?:|mailto:)/.test(target)) continue;
    const resolved = path.resolve(directory, decodeURIComponent(target));
    if (!fs.existsSync(resolved)) {
      errors.push(`${name}: broken link ${target}`);
    }
  }
}

for (const name of files.slice(0, 2)) {
  const content = markdown.get(name);
  if (!content) continue;
  const blocks = [...content.matchAll(/```mermaid\s*\n([\s\S]*?)\n```/g)];
  const openings = [...content.matchAll(/```mermaid\b/g)].length;
  if (blocks.length !== 1 || openings !== 1) {
    errors.push(`${name}: expected one closed Mermaid block`);
    continue;
  }
  const graph = blocks[0][1];
  if (!/^flowchart\s+(?:LR|RL|TB|TD|BT)\b/m.test(graph)) {
    errors.push(`${name}: expected a Mermaid flowchart declaration`);
  }
  const definitions = [...graph.matchAll(/\b([A-Z]{2}\d{2})\s*\[/g)].map((m) => m[1]);
  const defined = new Set(definitions);
  for (const id of defined) {
    if (definitions.filter((candidate) => candidate === id).length > 1) {
      errors.push(name + ": duplicate node definition " + id);
    }
  }
  const referenced = new Set([...graph.matchAll(/\b([A-Z]{2}\d{2})\b/g)].map((m) => m[1]));
  if (defined.size === 0) errors.push(`${name}: no stable component IDs`);
  for (const id of referenced) {
    if (!defined.has(id)) errors.push(`${name}: ${id} has no node definition`);
  }
  diagrams.set(name, defined);
}

const map = markdown.get("component-map.md");
if (map) {
  const rows = [...map.matchAll(/^\|\s*([A-Z]{2}\d{2})\s*\|/gm)].map((m) => m[1]);
  const mapped = new Set(rows);
  for (const id of mapped) {
    if (rows.filter((candidate) => candidate === id).length > 1) {
      errors.push("component-map.md: duplicate row " + id);
    }
  }
  const shown = new Set([...diagrams.values()].flatMap((ids) => [...ids]));
  for (const id of shown) {
    if (!mapped.has(id)) errors.push(`component-map.md: missing ${id}`);
  }
  for (const id of mapped) {
    if (!shown.has(id)) errors.push(`component-map.md: ${id} is absent from both diagrams`);
  }
}

if (errors.length) {
  for (const error of errors) process.stderr.write(`${error}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write("Architecture links, Mermaid blocks, and component IDs pass.\n");
}
