// Read-only Import bexio-Kontakte -> crm.db. Token nur aus Env (BEXIO_API_TOKEN), nie gespeichert.
// Aufruf: node import_bexio.mjs [--apply]   (ohne --apply = Dry-Run, schreibt nichts)
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { execFileSync } from "child_process";
const apply = process.argv.includes("--apply");
const t = new StdioClientTransport({ command: "npx", args: ["-y","github:nolen-ai/bexio-mcp"],
  env: { ...process.env, BEXIO_WRITE_MODE: "read-only", BEXIO_TOOL_GROUPS: "contacts" }, stderr: "ignore" });
const c = new Client({ name: "bernvapes-crm-import", version: "0.1" }); await c.connect(t);
let all = [], offset = 0;
for (;;) {
  const r = await c.callTool({ name: "bexio_contacts", arguments: { action: "list", limit: 25, offset } });
  const txt = r.content?.find(p=>p.type==="text")?.text ?? "[]";
  let d; try { d = JSON.parse(txt); } catch { try { d = JSON.parse(txt.slice(txt.indexOf("["), txt.lastIndexOf("]")+1)); } catch {} }
  if (d === undefined) { console.error("Antwort nicht JSON"); break; }
  const arr = Array.isArray(d) ? d : (d.data || d.contacts || d.items || Object.values(d).find(Array.isArray) || []);
  all.push(...arr); if (arr.length < 25) break; offset += 25;
}
await c.close();
const rows = all.map(o => ({ id: o.id, name: [o.name_2, o.name_1].filter(Boolean).join(" ").trim(),
  email: o.mail || null, phone: o.phone_mobile || o.phone_fixed || null }));
const q = s => s==null ? "NULL" : "'" + String(s).replace(/'/g,"''") + "'";
const sql = rows.map(r => `INSERT INTO customers(bexio_contact_id,name,email,phone) VALUES(${r.id},${q(r.name)},${q(r.email)},${q(r.phone)})
 ON CONFLICT(bexio_contact_id) DO UPDATE SET name=excluded.name,email=excluded.email,phone=excluded.phone,updated_at=CURRENT_TIMESTAMP;`).join("\n");
console.log(`bexio-Kontakte gelesen: ${rows.length} (mit E-Mail: ${rows.filter(r=>r.email).length}, mit Telefon: ${rows.filter(r=>r.phone).length})`);
if (!apply) { console.log("Dry-Run: nichts geschrieben. Mit --apply importieren."); process.exit(0); }
const py = "import sqlite3,sys;c=sqlite3.connect('crm.db');c.executescript(sys.stdin.read());print(c.execute('select count(*) from customers').fetchone()[0])";
const n = execFileSync("python3", ["-c", py], { input: "BEGIN;\n" + sql + "\nCOMMIT;" }).toString().trim();
console.log("Import fertig:", n, "Kunden in crm.db");
