// Plain server-rendered pages for signing in and administering the review site.
export const esc = (s: unknown) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

const CSS = `:root{--ink:#1c2330;--quiet:#5b6475;--line:#d9dde5;--bg:#f7f8fa;--card:#fff;--accent:#1f5fbf;--good:#1a7f4b;--bad:#b3261e;--warn:#9a6700}
*{box-sizing:border-box}body{font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);margin:0}
main{max-width:1000px;margin:0 auto;padding:24px 16px}.box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:24px}
.narrow{max-width:400px;margin:8vh auto 0}h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px}p{margin:8px 0}.muted{color:var(--quiet)}
label{display:block;font-size:13px;color:var(--quiet);margin:12px 0 4px}input,select{font:inherit;width:100%;padding:9px;border:1px solid var(--line);border-radius:8px;background:#fff}
button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer}button.primary{background:var(--accent);border-color:var(--accent);color:#fff;width:100%;margin-top:16px}
.err{color:var(--bad);margin-top:12px}.ok{color:var(--good)}table{width:100%;border-collapse:collapse;background:var(--card)}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{font-size:12px;color:var(--quiet)}.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;border:1px solid var(--line)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:end}.row>div{flex:1;min-width:150px}form.inline{display:inline}a{color:var(--accent)}
.link{font:13px ui-monospace,Menlo,monospace;word-break:break-all;background:#f1f5ff;border:1px solid #c7d7f5;border-radius:8px;padding:10px;user-select:all}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}`;

export function shell(title: string, body: string): string {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>${esc(title)} · Regulatory Studio review</title><style>${CSS}</style></head><body><main>${body}</main></body></html>`;
}

export const brand = `<p class="muted" style="margin:0 0 12px;font-size:13px">Regulatory Studio · jouleWise × Urja Praxis</p>`;

export function loginPage(base: string, error = "", email = ""): string {
  return shell("Sign in", `<div class="box narrow">${brand}<h1>Review sign-in</h1>
<form method="post" action="${base}/_/login"><label for="email">Work email</label><input id="email" name="email" type="email" autocomplete="username" required value="${esc(email)}">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required>
<button class="primary">Sign in</button>${error ? `<p class="err">${esc(error)}</p>` : ""}</form>
<p class="muted" style="margin-top:16px;font-size:13px">No account, or forgot your password? Ask the studio administrator for a new invitation link.</p></div>`);
}

export function invitePage(base: string, tokenValue: string, inv: { name: string; email: string } | null, error = ""): string {
  if (!inv) return shell("Invitation", `<div class="box narrow">${brand}<h1>This invitation link no longer works</h1>
<p>It may have been used already or have expired. Ask the studio administrator for a new one.</p><p><a href="${base}/_/login">Go to sign-in</a></p></div>`);
  return shell("Set your password", `<div class="box narrow">${brand}<h1>Welcome, ${esc(inv.name)}</h1><p class="muted">You will sign in as <b>${esc(inv.email)}</b>. Choose a password only you know.</p>
<form method="post" action="${base}/_/invite/${esc(tokenValue)}"><label for="password">New password (12 characters or more)</label>
<input id="password" name="password" type="password" autocomplete="new-password" minlength="12" required>
<label for="again">The same password again</label><input id="again" name="again" type="password" autocomplete="new-password" minlength="12" required>
<button class="primary">Set password and sign in</button>${error ? `<p class="err">${esc(error)}</p>` : ""}</form></div>`);
}

export function messagePage(title: string, text: string, link?: { href: string; label: string }): string {
  return shell(title, `<div class="box narrow">${brand}<h1>${esc(title)}</h1><p>${esc(text)}</p>${link ? `<p><a href="${esc(link.href)}">${esc(link.label)}</a></p>` : ""}</div>`);
}
