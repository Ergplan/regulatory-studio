// The review site. Reviewers sign in here; the pages they see are copies of the studio's review screen, pushed
// by the studio's Mac. A form they submit is saved as an event; the Mac collects events in order, applies each
// on the real review screen as that reviewer, and pushes the refreshed pages back. See pipeline/regstudio/mirror.py.
import { q, meta, NoDatabase, type Row } from "@/lib/review/db";
import { allowed, PERMISSIONS, checkPassword, cookieOf, COOKIE, currentUser, hashPassword, ipOf, lockedOut, passwordProblem, recordFailure,
  sessionCookie, sha, startSession, TEAMS, token, ROLES, ROLE_NAME, type Role, type Team, type User } from "@/lib/review/auth";
import { esc, invitePage, loginPage, messagePage, shell, brand } from "@/lib/review/ui";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

const NAME_SLOT = "RSREVIEWERNAME";
// Keep in step with ALLOWED in pipeline/regstudio/mirror.py; the Mac checks again before applying anything.
const FORMS = /^\/(?:order\/[0-9a-f]+\/(?:summary|link)|link\/\d+|regulation\/.+\/meta|clause\/.+|digest\/[0-9A-Za-z-]+(?:\/note)?|amendment\/[0-9a-f]+\/meta|amendment-change\/\d+|consultation\/[0-9a-f]+|(?:rating|impact|comments|checks|figures|notes|revise|commercial)\/[0-9a-f]+|(?:comment|revision|lesson)\/\d+|memory|deploy)$/;
const SECURITY = {
  "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
  "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; object-src 'self'; form-action 'self'; frame-ancestors 'self'; base-uri 'none'",
};
const TEAM_NAME: Record<string, string> = { urja: "Urja Praxis", joulewise: "jouleWise", admin: "Administrator" };

type Ctx = { req: Request; base: string; path: string; secure: boolean; host: string };

const html = (body: string, status = 200, extra: Record<string, string> = {}) =>
  new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8", ...SECURITY, ...extra } });
const go = (to: string, extra: Record<string, string> = {}) => new Response(null, { status: 303, headers: { Location: to, ...SECURITY, ...extra } });

function context(req: Request, parts: string[] | undefined): Ctx {
  const host = (req.headers.get("x-forwarded-host") || req.headers.get("host") || "").toLowerCase();
  const path = "/" + (parts ?? []).join("/");
  const proto = req.headers.get("x-forwarded-proto") || new URL(req.url).protocol.replace(":", "");
  return { req, base: host.startsWith("review.") ? "" : "/r", path, secure: proto === "https", host };
}

/** A form post must come from this site's own pages. */
function sameOrigin(c: Ctx): boolean {
  const origin = c.req.headers.get("origin");
  if (!origin) return (c.req.headers.get("sec-fetch-site") ?? "same-origin") === "same-origin";
  try {
    return new URL(origin).host.toLowerCase() === c.host;
  } catch {
    return false;
  }
}

async function form(req: Request): Promise<{ raw: string; data: URLSearchParams } | null> {
  const raw = await req.text();
  if (raw.length > 300_000) return null;
  return { raw, data: new URLSearchParams(raw) };
}

// ---------- the mirrored review pages ----------

function banner(c: Ctx, user: User, mac: any, events: Row[], queued: string | null): string {
  const seen = mac?.at ? (Date.now() - Date.parse(mac.at)) / 1000 : Infinity;
  const bits: string[] = [];
  if (seen > 180) bits.push(`<div class="flash" role="status"><b>The studio's server is not connected right now</b>${mac?.at ? ` (last heard from ${esc(new Date(mac.at).toISOString().slice(0, 16).replace("T", " "))} UTC)` : ""}. You can keep working: what you submit is saved here and applied as soon as it is back.</div>`);
  for (const e of events) {
    if (!e.applied_at) bits.push(`<div class="flash" role="status" data-pending="${e.id}">Saved. Applying your change on the studio's server, usually within a minute. This page refreshes by itself.</div>`);
    else if (e.status !== "applied") bits.push(`<div class="flash" role="alert" style="border-color:#b3261e;background:#fdecea"><b>A change you submitted was not applied.</b> ${esc(e.note || "")} Please check the page and try again.</div>`);
  }
  const admin = (user.team === "urja" ? "" : ` · <a href="${c.base}/_/inbox">Inbox</a>`) + (user.team === "admin" ? ` · <a href="${c.base}/_/admin">Admin</a>` : "");
  const who = `<div class="muted" data-rs-base="${esc(c.base)}" style="font-size:12px;margin:0 0 10px">${esc(TEAM_NAME[user.team])}${user.role === "senior" ? " · Senior reviewer" : ""} · ${esc(user.email)}${admin}</div>`;
  const script = `<script>(function(){var p=document.querySelector('[data-pending]');if(!p)return;var id=p.getAttribute('data-pending'),n=0;
function t(){n++;fetch(${JSON.stringify(c.base)}+'/_/event/'+id+'?page='+encodeURIComponent(${JSON.stringify(c.path)}),{credentials:'same-origin',cache:'no-store'}).then(function(r){return r.json()}).then(function(s){
if(s.done&&(s.fresh||s.waited>25)){location.replace(location.pathname+location.hash)}else if(n<90){setTimeout(t,n<10?3000:6000)}}).catch(function(){if(n<90)setTimeout(t,6000)})}setTimeout(t,2500)})();</script>`;
  return who + bits.join("") + controls(c, user) + (queued || events.some((e) => !e.applied_at) ? script : "");
}

/** Disables, with a short note, the buttons this person's team or role cannot use. The Mac refuses them anyway;
 *  this only saves the click. Runs on load and after each in-place update. */
function controls(c: Ctx, user: User): string {
  const cfg = JSON.stringify({ base: c.base, team: user.team, senior: user.role === "senior", rules: PERMISSIONS }).replace(/</g, "\\u003c");
  return `<style>.rs-lock{display:block;margin-top:6px;font-size:12px;color:#5b6475}button[disabled].rs-locked{opacity:.45;cursor:not-allowed}</style>
<script>(function(){var C=${cfg};function ok(path){for(var i=0;i<C.rules.length;i++){if(new RegExp(C.rules[i].path).test(path))return C.rules[i].teams.indexOf(C.team)>=0?null:C.rules[i].who}return null}
function lock(f,why){if(f.getAttribute('data-locked'))return;f.setAttribute('data-locked','1');f.querySelectorAll('button,input[type=submit]').forEach(function(b){b.disabled=true;b.classList.add('rs-locked')});
var n=document.createElement('span');n.className='rs-lock';n.textContent=why;f.appendChild(n)}
function run(){document.querySelectorAll('form[method=post]').forEach(function(f){var a=(f.getAttribute('action')||'').slice(C.base.length);var who=ok(a);
if(who){lock(f,'Decided by '+who+'. You can still comment.');return}
if(!C.senior&&f.getAttribute('data-held')){lock(f,'Final decision by '+f.getAttribute('data-held')+' (senior reviewer). You can still comment.');return}
if(!C.senior){var card=f.closest('.card');if(card&&card.querySelector('.held')&&a.indexOf('/notes/')!==0&&a.indexOf('/comment/')!==0)lock(f,'A senior reviewer has made the final decision here. You can still comment.')}})}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();document.addEventListener('rs:updated',run)})();</script>`;
}

async function page(c: Ctx, user: User): Promise<Response> {
  const row = (await q("SELECT html FROM rs_pages WHERE path = $1", [c.path]))[0];
  if (!row) {
    const any = Number((await q("SELECT count(*) AS n FROM rs_pages"))[0].n);
    return html(messagePage(any ? "Page not found" : "Nothing to review yet",
      any ? "This item is not on the review site. It may have been removed from the queue." : "The studio's server has not sent its review pages yet. They appear here a minute or so after it connects.",
      { href: c.base || "/", label: "Go to the review hub" }), any ? 404 : 200);
  }
  const events = await q(
    `SELECT id, applied_at, status, note FROM rs_events WHERE user_id = $1 AND page = $2
       AND (applied_at IS NULL OR (status <> 'applied' AND applied_at > now() - interval '10 minutes')) ORDER BY id DESC LIMIT 4`, [user.id, c.path]);
  let out: string = row.html.split(NAME_SLOT).join(esc(user.name));
  if (c.base) {
    out = out.replace(/\b(href|action|src)="\//g, `$1="${c.base}/`).replace(/'\/file\//g, `'${c.base}/file/`);
  }
  const b = banner(c, user, await meta("mac"), events, new URL(c.req.url).searchParams.get("queued"));
  out = out.includes("<main>") ? out.replace("<main>", "<main>" + b) : b + out;
  return html(out);
}

async function file(c: Ctx): Promise<Response> {
  const id = c.path.slice("/file/".length);
  if (!/^[0-9a-f]{64}$/.test(id)) return html(messagePage("Not found", "No such file."), 404);
  const parts = await q("SELECT n, total, data FROM rs_files WHERE id = $1 ORDER BY n", [id]);
  if (!parts.length || !parts[0].total || parts.length < parts[0].total) {
    return html(shell("PDF", `<p class="muted" style="padding:24px">${parts.length && !parts[0].total
      ? "This order's PDF is too large to show here. Use the Source link above the summary to open it on the commission's website. The passages cited on this page are shown below when you click a paragraph number."
      : "The PDF is still being copied from the studio's server. It should appear within a few minutes."}</p>`));
  }
  return new Response(Buffer.concat(parts.map((p) => p.data as Buffer)), { headers: { "Content-Type": "application/pdf", "Content-Disposition": "inline", ...SECURITY,
    "Content-Security-Policy": "default-src 'none'; object-src 'self'; plugin-types application/pdf; frame-ancestors 'self'" } });
}

// ---------- sign-in, invitations, administration ----------

async function login(c: Ctx): Promise<Response> {
  const f = await form(c.req);
  if (!f || !sameOrigin(c)) return html(loginPage(c.base, "Please try again."), 400);
  const email = (f.data.get("email") || "").trim().toLowerCase(), pw = f.data.get("password") || "", ip = ipOf(c.req);
  if (await lockedOut(email, ip)) return html(loginPage(c.base, "Too many attempts. Wait 15 minutes and try again.", email), 429);
  const u = (await q("SELECT id, pw_hash, active FROM rs_users WHERE email = $1", [email]))[0];
  const ok = await checkPassword(pw, u?.pw_hash ?? null);
  if (!u || !u.active || !ok) {
    await recordFailure(email, ip);
    return html(loginPage(c.base, "That email and password do not match.", email), 401);
  }
  return go(c.base || "/", { "Set-Cookie": sessionCookie(await startSession(Number(u.id)), c.secure) });
}

async function invitation(c: Ctx, method: string): Promise<Response> {
  const t = c.path.slice("/_/invite/".length);
  const inv = /^[A-Za-z0-9_-]{20,80}$/.test(t)
    ? (await q("SELECT email, name, team, role FROM rs_invites WHERE token_hash = $1 AND used_at IS NULL AND expires_at > now()", [sha(t)]))[0] : null;
  if (method === "GET" || !inv) return html(invitePage(c.base, t, (inv as any) ?? null), inv ? 200 : 410);
  const f = await form(c.req);
  if (!f || !sameOrigin(c)) return html(invitePage(c.base, t, inv as any, "Please try again."), 400);
  const pw = f.data.get("password") || "";
  const problem = pw !== (f.data.get("again") || "") ? "The two passwords are not the same." : passwordProblem(pw, inv.email);
  if (problem) return html(invitePage(c.base, t, inv as any, problem), 400);
  const used = await q("UPDATE rs_invites SET used_at = now() WHERE token_hash = $1 AND used_at IS NULL RETURNING email", [sha(t)]);
  if (!used.length) return html(invitePage(c.base, t, null), 410);
  const u = (await q(
    `INSERT INTO rs_users(email, name, team, role, pw_hash) VALUES ($1, $2, $3, $4, $5)
     ON CONFLICT (email) DO UPDATE SET name = excluded.name, team = excluded.team, role = excluded.role, pw_hash = excluded.pw_hash, active = true RETURNING id`,
    [inv.email, inv.name, inv.team, ROLES.includes(inv.role) ? inv.role : "reviewer", await hashPassword(pw)]))[0];
  await q("DELETE FROM rs_sessions WHERE user_id = $1", [u.id]);            // a new password signs out old sessions
  return go(c.base || "/", { "Set-Cookie": sessionCookie(await startSession(Number(u.id)), c.secure) });
}

async function admin(c: Ctx, user: User, method: string): Promise<Response> {
  if (user.team !== "admin") return html(messagePage("Administrators only", "Ask the studio administrator if you need something changed.", { href: c.base || "/", label: "Back to the review hub" }), 403);
  let note = "";
  if (method === "POST") {
    const f = await form(c.req);
    if (!f || !sameOrigin(c)) return html(messagePage("Not accepted", "Please go back and try again."), 400);
    const d = f.data, action = d.get("action");
    if (action === "invite" || action === "invite_email") {
      const email = (d.get("email") || "").trim().toLowerCase(), name = (d.get("name") || "").trim().slice(0, 80), team = d.get("team") as Team;
      const role: Role = d.get("role") === "senior" ? "senior" : "reviewer";
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || !name || !TEAMS.includes(team)) note = `<p class="err">Enter a name, a valid email and a team.</p>`;
      else if (action === "invite_email") {
        await q(`INSERT INTO rs_invite_requests(name, email, team, role, requested_by) VALUES ($1, $2, $3, $4, $5)`, [name, email, team, role, user.email]);
        note = `<div class="box" style="margin:12px 0"><b>Invitation for ${esc(name)} will be emailed</b><p class="muted">The studio's server creates the link and emails it to ${esc(email)} within a minute or two. The result shows below under "Emailed invitations".</p></div>`;
      } else {
        const t = token();
        await q(`INSERT INTO rs_invites(token_hash, email, name, team, role, expires_at, created_by) VALUES ($1, $2, $3, $4, $5, now() + interval '7 days', $6)`, [sha(t), email, name, team, role, user.email]);
        const origin = `${c.secure ? "https" : "http"}://${c.host}`;
        note = `<div class="box" style="margin:12px 0"><b>Invitation for ${esc(name)}</b><p class="muted">Send them this link. It works once, for 7 days, and is not shown again. They choose their own password.</p><div class="link">${esc(origin + c.base + "/_/invite/" + t)}</div></div>`;
      }
    } else if (action === "active" || action === "team" || action === "role") {
      const id = Number(d.get("id"));
      if (id === user.id) note = `<p class="err">You cannot change your own account here.</p>`;
      else if (action === "active") {
        await q("UPDATE rs_users SET active = $2 WHERE id = $1", [id, d.get("value") === "1"]);
        await q("DELETE FROM rs_sessions WHERE user_id = $1", [id]);
      } else if (action === "role") {
        if (ROLES.includes(d.get("value") as Role)) await q("UPDATE rs_users SET role = $2 WHERE id = $1", [id, d.get("value")]);
      } else if (TEAMS.includes(d.get("value") as Team)) await q("UPDATE rs_users SET team = $2 WHERE id = $1", [id, d.get("value")]);
    } else if (action === "revoke") await q("DELETE FROM rs_invites WHERE token_hash = $1", [d.get("id")]);
  }
  const [users, invites, events, mac, pages, asked] = await Promise.all([
    q("SELECT id, email, name, team, role, active, last_login FROM rs_users ORDER BY active DESC, name"),
    q("SELECT token_hash, email, name, team, role, expires_at FROM rs_invites WHERE used_at IS NULL AND expires_at > now() ORDER BY created_at DESC"),
    q("SELECT id, path, user_name, created_at, applied_at, status, note FROM rs_events ORDER BY id DESC LIMIT 40"),
    meta("mac"), q("SELECT count(*) AS n, max(updated_at) AS at FROM rs_pages"),
    q("SELECT name, email, team, at, done_at, status, note FROM rs_invite_requests ORDER BY id DESC LIMIT 10")]);
  const mailFrom: string | null = mac?.status?.mail ?? null;
  const when = (d: any) => (d ? new Date(d).toISOString().slice(0, 16).replace("T", " ") + " UTC" : "never");
  const act = `${c.base}/_/admin`;
  const seen = mac?.at ? Math.round((Date.now() - Date.parse(mac.at)) / 1000) : null;
  const body = `${brand}<h1>Review site administration</h1><p><a href="${c.base || "/"}">Back to the review hub</a></p>${note}
<h2>The studio's server</h2><div class="box"><p>${seen === null ? `<span class="err">It has never connected.</span>` : seen < 180 ? `<span class="ok">Connected.</span> Last check-in ${seen} seconds ago.` : `<span class="err">Not connected.</span> Last heard from ${esc(when(mac.at))}.`}
 ${Number(pages[0].n)} review pages here, last updated ${esc(when(pages[0].at))}. Last scan: ${esc(mac?.status?.scan?.finished ? when(mac.status.scan.finished) : "not recorded")}.</p></div>
<h2>Invite a reviewer</h2><form method="post" action="${act}" class="box"><div class="row">
<div><label for="name">Full name</label><input id="name" name="name" required maxlength="80"></div><div><label for="email">Work email</label><input id="email" name="email" type="email" required></div>
<div><label for="team">Team</label><select id="team" name="team"><option value="urja">Urja Praxis (legal review)</option><option value="joulewise">jouleWise (commercial review)</option><option value="admin">Administrator</option></select></div>
<div><label for="role">Review role</label><select id="role" name="role"><option value="reviewer">Reviewer</option><option value="senior">Senior reviewer (decisions take precedence)</option></select></div>
<div style="flex:0;display:flex;gap:8px;flex-wrap:wrap">${mailFrom ? `<button name="action" value="invite_email" style="white-space:nowrap">Email the invitation</button>` : ""}<button name="action" value="invite" style="white-space:nowrap">Show the link</button></div></div>
<p class="muted" style="margin:8px 0 0">${mailFrom ? `"Email the invitation" sends it from ${esc(mailFrom)}. "Show the link" lets you send it yourself.` : `Emailing invitations is not set up on the studio's server yet, so send the link yourself.`}</p></form>
${asked.length ? `<h2>Emailed invitations</h2><table><tr><th>Name</th><th>Email</th><th>Asked</th><th>Result</th></tr>${asked.map((a) => `<tr><td>${esc(a.name)}</td><td>${esc(a.email)}</td><td>${esc(when(a.at))}</td><td>${a.done_at ? (a.status === "emailed" ? `<span class="ok">emailed</span>` : `<span class="err">${esc(a.status)}</span> ${esc(a.note)}`) : "waiting for the studio's server"}</td></tr>`).join("")}</table>` : ""}
<h2>Reviewers</h2><table><tr><th>Name</th><th>Email</th><th>Team</th><th>Review role</th><th>Last sign-in</th><th></th></tr>
${users.map((u) => `<tr><td>${esc(u.name)}${u.active ? "" : ` <span class="pill">switched off</span>`}</td><td>${esc(u.email)}</td>
<td><form method="post" action="${act}" class="inline"><input type="hidden" name="action" value="team"><input type="hidden" name="id" value="${u.id}"><select name="value" onchange="this.form.submit()" style="width:auto" ${Number(u.id) === user.id ? "disabled" : ""}>${TEAMS.map((t) => `<option value="${t}" ${t === u.team ? "selected" : ""}>${TEAM_NAME[t]}</option>`).join("")}</select></form></td>
<td><form method="post" action="${act}" class="inline"><input type="hidden" name="action" value="role"><input type="hidden" name="id" value="${u.id}"><select name="value" onchange="this.form.submit()" style="width:auto" ${Number(u.id) === user.id ? "disabled" : ""}>${ROLES.map((r) => `<option value="${r}" ${r === u.role ? "selected" : ""}>${ROLE_NAME[r]}</option>`).join("")}</select></form></td>
<td>${esc(when(u.last_login))}</td><td>${Number(u.id) === user.id ? "" : `<form method="post" action="${act}" class="inline"><input type="hidden" name="action" value="active"><input type="hidden" name="id" value="${u.id}"><input type="hidden" name="value" value="${u.active ? 0 : 1}"><button>${u.active ? "Switch off" : "Switch on"}</button></form>`}</td></tr>`).join("") || `<tr><td colspan="6" class="muted">Nobody yet.</td></tr>`}</table>
<p class="muted">Review role: a senior reviewer's decisions take precedence, and other reviewers cannot change them (they can still comment). To reset someone's password, create a new invitation for the same email; it sets the team and role chosen there.</p>
<h2>Invitations not yet used</h2><table><tr><th>Name</th><th>Email</th><th>Team</th><th>Expires</th><th></th></tr>
${invites.map((i) => `<tr><td>${esc(i.name)}</td><td>${esc(i.email)}</td><td>${esc(TEAM_NAME[i.team])}${i.role === "senior" ? " · Senior reviewer" : ""}</td><td>${esc(when(i.expires_at))}</td><td><form method="post" action="${act}" class="inline"><input type="hidden" name="action" value="revoke"><input type="hidden" name="id" value="${esc(i.token_hash)}"><button>Cancel</button></form></td></tr>`).join("") || `<tr><td colspan="5" class="muted">None.</td></tr>`}</table>
<h2>Recent activity</h2><table><tr><th>When</th><th>Who</th><th>What</th><th>Result</th></tr>
${events.map((e) => `<tr><td>${esc(when(e.created_at))}</td><td>${esc(e.user_name)}</td><td>${esc(e.path)}</td><td>${e.applied_at ? (e.status === "applied" ? `<span class="ok">applied</span>` : `<span class="err">${esc(e.status)}</span> ${esc(e.note)}`) : "waiting for the studio's server"}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Nothing yet.</td></tr>`}</table>`;
  return html(shell("Administration", body));
}

// Messages from the public site: the chat box and "Discuss my project". Readable by the jouleWise team and administrators.
async function inbox(c: Ctx, user: User, method: string): Promise<Response> {
  if (user.team === "urja") return html(messagePage("jouleWise team only", "Messages from the public site are handled by the jouleWise team.", { href: c.base || "/", label: "Back to the review hub" }), 403);
  if (method === "POST") {
    const f = await form(c.req);
    if (!f || !sameOrigin(c)) return html(messagePage("Not accepted", "Please go back and try again."), 400);
    const kind = f.data.get("kind"), id = f.data.get("id") || "", done = f.data.get("done") === "1";
    if (kind === "chat") await q("UPDATE rs_chats SET handled_by = $2, handled_at = CASE WHEN $3 THEN now() END WHERE id = $1", [id, done ? user.name : null, done]);
    if (kind === "lead") await q("UPDATE rs_leads SET handled_by = $2, handled_at = CASE WHEN $3 THEN now() END WHERE id = $1", [Number(id), done ? user.name : null, done]);
    return go(`${c.base}/_/inbox`);
  }
  const [chats, leads] = await Promise.all([
    q("SELECT * FROM rs_chats ORDER BY (handled_at IS NOT NULL), updated_at DESC LIMIT 100"),
    q("SELECT * FROM rs_leads ORDER BY (handled_at IS NOT NULL), at DESC LIMIT 100")]);
  const when = (d: any) => (d ? new Date(d).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }) : "");
  const act = `${c.base}/_/inbox`;
  const mark = (kind: string, id: any, done: boolean) => `<form method="post" action="${act}" class="inline"><input type="hidden" name="kind" value="${kind}"><input type="hidden" name="id" value="${esc(id)}"><input type="hidden" name="done" value="${done ? 1 : 0}"><button>${done ? "Mark handled" : "Reopen"}</button></form>`;
  const open = chats.filter((x) => !x.handled_at).length + leads.filter((x) => !x.handled_at).length;
  const body = `${brand}<h1>Inbox</h1><p><a href="${c.base || "/"}">Back to the review hub</a> · ${open} waiting for a reply</p>
<h2>Project review requests</h2><table><tr><th>When</th><th>From</th><th>About</th><th>Message</th><th></th></tr>
${leads.map((l) => `<tr${l.handled_at ? ' class="muted"' : ""}><td>${esc(when(l.at))}</td><td><b>${esc(l.name)}</b><br><a href="mailto:${esc(l.email)}">${esc(l.email)}</a><br>${esc(l.org || "")}${l.business ? `<br><span class="muted">${esc(l.business)}${l.state ? `, ${esc(l.state)}` : ""}</span>` : ""}</td>
<td>${esc(l.asked || l.reading || "-")}${l.page ? `<br><a href="${esc(l.page)}" target="_blank" rel="noopener">page</a>` : ""}</td><td style="white-space:pre-wrap">${esc(l.message || "")}</td>
<td>${l.handled_at ? `<span class="muted">handled by ${esc(l.handled_by)}</span><br>${mark("lead", l.id, false)}` : mark("lead", l.id, true)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">None yet.</td></tr>`}</table>
<h2>Chat conversations</h2><table><tr><th>Last message</th><th>Visitor</th><th>Conversation</th><th></th></tr>
${chats.map((x) => `<tr${x.handled_at ? ' class="muted"' : ""}><td>${esc(when(x.updated_at))}<br><span class="muted">on ${esc(x.page || "/")}</span></td>
<td>${x.reach ? `<b>${esc(x.name || "")}</b>${x.company ? `<br>${esc(x.company)}` : ""}<br>${esc(x.reach)}` : `<span class="muted">no contact left</span>`}</td>
<td>${(x.messages || []).map((m: any) => `<p style="margin:0 0 6px">${esc(m.text)}</p>`).join("")}</td>
<td>${x.handled_at ? `<span class="muted">handled by ${esc(x.handled_by)}</span><br>${mark("chat", x.id, false)}` : mark("chat", x.id, true)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">None yet.</td></tr>`}</table>`;
  return html(shell("Inbox", body));
}

async function submit(c: Ctx, user: User): Promise<Response> {
  if (!sameOrigin(c)) return html(messagePage("Not accepted", "This form did not come from the review site. Go back, reload the page and try again."), 403);
  if (!FORMS.test(c.path) || c.path.includes("..")) return html(messagePage("Not accepted", "The review site does not accept this form."), 404);
  if (!allowed(user.team, c.path)) {
    return html(messagePage("This decision belongs to another team",
      c.path.startsWith("/commercial/") ? "Commercial illustrations are approved by the jouleWise commercial team." : "Legal summaries, links and editions are decided by the Urja Praxis legal team. You can still leave a comment.",
      { href: c.base || "/", label: "Back to the review hub" }), 403);
  }
  const f = await form(c.req);
  if (!f) return html(messagePage("Too large", "That is more text than the review site accepts in one form."), 413);
  let pagePath = "/";
  try {
    const ref = new URL(c.req.headers.get("referer") || "", "http://x");
    pagePath = decodeURIComponent(ref.pathname).replace(c.base ? new RegExp("^" + c.base) : /^$/, "") || "/";
  } catch { /* keep "/" */ }
  const dup = (await q(`SELECT id FROM rs_events WHERE user_id = $1 AND path = $2 AND body = $3 AND applied_at IS NULL AND created_at > now() - interval '15 seconds'`, [user.id, c.path, f.raw]))[0];
  const id = dup?.id ?? (await q(
    `INSERT INTO rs_events(path, body, page, user_id, user_name, user_email, team, role) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id`,
    [c.path, f.raw, pagePath, user.id, user.name, user.email, user.team, user.role]))[0].id;
  return go(`${c.base}${encodeURI(pagePath)}?queued=${id}`);
}

async function eventStatus(c: Ctx, user: User): Promise<Response> {
  const id = Number(c.path.slice("/_/event/".length));
  const e = (await q("SELECT applied_at, status, note FROM rs_events WHERE id = $1 AND user_id = $2", [id, user.id]))[0];
  if (!e) return Response.json({ done: true, fresh: true }, { headers: SECURITY });
  const pagePath = new URL(c.req.url).searchParams.get("page") || "/";
  const p = (await q("SELECT updated_at FROM rs_pages WHERE path = $1", [pagePath]))[0];
  const done = !!e.applied_at;
  const pushed = (await meta("pushed"))?.at;   // the Mac's last complete push of pages, changed or not
  const fresh = done && (e.status !== "applied" || !p || new Date(p.updated_at) >= new Date(e.applied_at)
    || (!!pushed && new Date(pushed) >= new Date(e.applied_at)));
  return Response.json({ done, status: e.status, note: e.status && e.status !== "applied" ? e.note : undefined, fresh,
    waited: done ? (Date.now() - new Date(e.applied_at).getTime()) / 1000 : 0 }, { headers: SECURITY });
}

async function handle(req: Request, parts: string[] | undefined, method: "GET" | "POST"): Promise<Response> {
  const c = context(req, parts);
  try {
    if (c.path === "/login") return go(c.base + "/_/login");
    if (c.path === "/_/login") return method === "POST" ? login(c) : (await currentUser(req)) ? go(c.base || "/") : html(loginPage(c.base));
    if (c.path.startsWith("/_/invite/")) return invitation(c, method);
    if (c.path === "/logout" || c.path === "/_/logout") {
      const sid = cookieOf(req, COOKIE);
      if (sid) await q("DELETE FROM rs_sessions WHERE token_hash = $1", [sha(sid)]);
      return go(c.base + "/_/login", { "Set-Cookie": sessionCookie("", c.secure, 0) });
    }
    const user = await currentUser(req);
    if (!user) return method === "GET" ? go(c.base + "/_/login") : html(loginPage(c.base, "Your session has ended. Sign in and submit the form again."), 401);
    if (c.path === "/_/admin") return admin(c, user, method);
    if (c.path === "/_/inbox") return inbox(c, user, method);
    if (method === "POST") return submit(c, user);
    if (c.path.startsWith("/_/event/")) return eventStatus(c, user);
    if (c.path.startsWith("/file/")) return file(c);
    if (c.path.startsWith("/_/")) return html(messagePage("Page not found", "There is nothing at this address.", { href: c.base || "/", label: "Go to the review hub" }), 404);
    return page(c, user);
  } catch (e) {
    if (e instanceof NoDatabase) return html(messagePage("The review site is being set up", "Its database is not connected yet. Please try again later."), 503);
    console.error("review", c.path, e);
    return html(messagePage("Something went wrong", "The review site could not finish that. Nothing was changed. Please try again in a moment."), 500);
  }
}

type P = { params: Promise<{ path?: string[] }> };
export async function GET(req: Request, { params }: P) { return handle(req, (await params).path, "GET"); }
export async function POST(req: Request, { params }: P) { return handle(req, (await params).path, "POST"); }
