'use client';

import { FormEvent, useCallback, useMemo, useState } from "react";

type Section = "overview" | "examinations" | "candidates" | "staff" | "custody" | "integrity" | "cases" | "audit";
type Row = Record<string, unknown>;
type Examination = { id: string; code: string; title: string; level: string; subject: string; exam_date: string; status: string };
type Finding = { id: string; examination_id: string; candidate_a_id: string; candidate_b_id: string; similarity_score: number; status: string; evidence: { comparable_question_count?: number; matching_question_count?: number; exact_agreement?: number; matched_question_ids?: string[] } };
type CaseRecord = { id: string; finding_id: string; affected_candidate_id: string; status: string; outcome?: string | null; created_at?: string };

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const sections: { id: Section; label: string; icon: string; description: string }[] = [
  { id: "overview", label: "Overview", icon: "◫", description: "System health and operational posture" },
  { id: "examinations", label: "Examinations", icon: "▤", description: "Create and review examination sessions" },
  { id: "candidates", label: "Candidates", icon: "♙", description: "Registration and attendance records" },
  { id: "staff", label: "Staff integrity", icon: "♧", description: "Eligibility reviews and assignments" },
  { id: "custody", label: "Paper custody", icon: "⬡", description: "Track controlled paper-batch handovers" },
  { id: "integrity", label: "Answer analysis", icon: "⌕", description: "Review explainable similarity signals" },
  { id: "cases", label: "Cases & appeals", icon: "☷", description: "Independent decisions and appeals" },
  { id: "audit", label: "Audit integrity", icon: "⛨", description: "Inspect the event-chain linkage status" },
];

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init.headers || {}) },
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`);
  return body as T;
}

function IconMark() { return <div className="brand-mark" aria-hidden="true"><span>R</span><i>✓</i></div>; }

function DataTable({ rows, columns, empty }: { rows: Row[]; columns: string[]; empty: string }) {
  if (!rows.length) return <div className="empty-state"><div className="empty-icon">⌁</div><strong>No records yet</strong><p>{empty}</p></div>;
  return <div className="table-wrap"><table><thead><tr>{columns.map((c) => <th key={c}>{c.replaceAll("_", " ")}</th>)}</tr></thead><tbody>
    {rows.map((row, i) => <tr key={String(row.id ?? i)}>{columns.map((c) => {
      const value = row[c];
      const shown = value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
      return <td key={c}>{c === "status" || c === "outcome" ? <span className={`status-pill ${shown.toLowerCase().replaceAll("_", "-")}`}>{shown.replaceAll("_", " ")}</span> : shown.length > 72 ? shown.slice(0, 69) + "…" : shown}</td>;
    })}</tr>)}
  </tbody></table></div>;
}

export default function Home() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<{ full_name: string; role: string; email: string } | null>(null);
  const [section, setSection] = useState<Section>("overview");
  const [examinations, setExaminations] = useState<Examination[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [audit, setAudit] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [latestBatchId, setLatestBatchId] = useState("");
  const [selectedExam, setSelectedExam] = useState("");
  const [candidateRows, setCandidateRows] = useState<Row[]>([]);
  const active = useMemo(() => sections.find((item) => item.id === section)!, [section]);

  const load = useCallback(async (accessToken: string) => {
    try { setExaminations(await request<Examination[]>("/examinations", accessToken)); } catch (e) { setError((e as Error).message); }
    try { setFindings(await request<Finding[]>("/integrity/findings?limit=100", accessToken)); } catch { setFindings([]); }
    try { setCases(await request<CaseRecord[]>("/cases?limit=100", accessToken)); } catch { setCases([]); }
    try { setAudit(await request<Row>("/audit/status", accessToken)); } catch { setAudit(null); }
  }, []);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(API + "/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: email, password }),
        cache: "no-store",
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Sign-in failed");
      setToken(body.access_token);
      const profile = await request<{ full_name: string; role: string; email: string }>("/auth/me", body.access_token);
      setUser(profile); setPassword(""); await load(body.access_token); setMessage("Signed in. Records loaded from the API.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function submitAction(event: FormEvent<HTMLFormElement>, path: string, method: string, build: (form: FormData) => Row, success: string) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      await request(path, token, { method, body: JSON.stringify(build(form)) });
      setMessage(success);
      await load(token);
      if (section === "integrity") setSection("integrity");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function examOptions() {
    return <select name="examination_id" required value={selectedExam} onChange={(e) => setSelectedExam(e.target.value)}><option value="">Select an examination…</option>{examinations.map((e) => <option key={e.id} value={e.id}>{e.code} · {e.subject} · {e.exam_date}</option>)}</select>;
  }

  if (!token || !user) return <main className="login-shell">
    <div className="login-art"><div className="art-glow glow-one" /><div className="art-glow glow-two" /><div className="art-grid" />
      <div className="login-art-content"><IconMark /><p className="eyebrow light">RWANDA · NATIONAL EXAMINATIONS</p><h1>Trust the result.<br /><em>Verify the process.</em></h1><p className="art-copy">A secure operational workspace for examination integrity, accountable evidence and fair review.</p>
        <div className="art-footer"><span><i /> Controlled access</span><span><i /> Evidence-led</span><span><i /> Human decisions</span></div>
      </div>
    </div>
    <div className="login-panel"><div className="login-card"><div className="mobile-brand"><IconMark /><span>Exam Integrity</span></div><p className="eyebrow">SECURE OFFICIAL ACCESS</p><h2>Welcome back</h2><p className="muted">Sign in using your authorized platform account.</p>
      <form className="stack-form" onSubmit={login}><label>Official email<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@institution.gov.rw" /></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" /></label><button className="primary-btn full" disabled={busy}>{busy ? "Verifying access…" : "Sign in securely"} <span>→</span></button></form>
      {error && <div className="alert error">{error}</div>}{message && <div className="alert success">{message}</div>}<p className="login-note"><span>⛨</span> Access and actions are logged. Never share credentials or use public devices for sensitive work.</p>
    </div><p className="legal-line">Examination Integrity Platform · Authorized use only</p></div>
  </main>;

  const latestFindings = findings.slice(0, 5);
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-lockup"><IconMark /><div><strong>Exam Integrity</strong><small>RWANDA PLATFORM</small></div></div>
      <div className="side-label">WORKSPACE</div><nav>{sections.map((item) => <button key={item.id} className={section === item.id ? "nav-item active" : "nav-item"} onClick={() => { setSection(item.id); setMessage(""); setError(""); }}><span className="nav-icon">{item.icon}</span>{item.label}{item.id === "integrity" && findings.length > 0 && <b>{findings.length}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="secure-indicator"><span /> API connection active</div><div className="profile-row"><div className="avatar">{user.full_name.split(" ").map((s) => s[0]).slice(0,2).join("").toUpperCase()}</div><div className="profile-meta"><strong>{user.full_name}</strong><small>{user.role.replaceAll("_", " ")}</small></div><button className="icon-btn" title="Sign out" onClick={() => { setToken(""); setUser(null); setExaminations([]); setFindings([]); setCases([]); setAudit(null); }}>↪</button></div></div>
    </aside>
    <main className="main-panel">
      <header className="topbar"><div className="breadcrumb">National operations <span>/</span> {active.label}</div><div className="top-actions"><span className="env-tag">SECURE SESSION</span><button className="icon-btn refresh-btn" title="Refresh live data" onClick={() => load(token)}>↻</button><div className="date-chip">{new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</div></div></header>
      <div className="page-content">
        <div className="page-heading"><div><p className="eyebrow">NATIONAL EXAMINATION OVERSIGHT</p><h1>{active.label}</h1><p className="muted">{active.description}</p></div><div className="heading-actions"><span className="live-dot">Live API data</span><button className="outline-btn" onClick={() => load(token)}>↻ Refresh data</button></div></div>
        {error && <div className="alert error">{error}<button onClick={() => setError("")}>×</button></div>}
        {message && <div className="alert success">{message}<button onClick={() => setMessage("")}>×</button></div>}
        {section === "overview" && <>
          <div className="welcome-strip"><div><span className="welcome-icon">✳</span><div><strong>Integrity operations, connected.</strong><p>Use verified records and corroborating evidence. An analytics alert is a review lead—not a verdict.</p></div></div><span className="strip-tag">HUMAN REVIEW REQUIRED</span></div>
          <div className="metric-grid">
            <div className="metric-card"><div className="metric-top"><span>Examination sessions</span><i>▤</i></div><strong>{examinations.length}</strong><small>Recorded in the API</small><div className="metric-line green" /></div>
            <div className="metric-card"><div className="metric-top"><span>Review leads</span><i>⌕</i></div><strong>{findings.length}</strong><small>Require authorized human review</small><div className="metric-line amber" /></div>
            <div className="metric-card"><div className="metric-top"><span>Open / active cases</span><i>☷</i></div><strong>{cases.filter((c) => !["CLOSED"].includes(c.status)).length}</strong><small>Decision and appeal workflow</small><div className="metric-line blue" /></div>
            <div className="metric-card"><div className="metric-top"><span>Audit chain</span><i>⛨</i></div><strong className={audit?.valid === true ? "good-text" : "neutral-text"}>{audit?.valid === true ? "Valid" : audit ? "Check" : "—"}</strong><small>{audit?.event_count ? `${audit.event_count} recorded events` : "Authorized audit view"}</small><div className="metric-line green" /></div>
          </div>
          <div className="content-grid"><section className="panel"><div className="panel-head"><div><h3>Recent examination sessions</h3><p>Latest records returned by the API</p></div><button className="text-btn" onClick={() => setSection("examinations")}>View all →</button></div><DataTable rows={examinations.slice(0,5) as unknown as Row[]} columns={["code","subject","level","exam_date","status"]} empty="Create your first authorized examination session." /></section>
          <section className="panel signal-panel"><div className="panel-head"><div><h3>Integrity review queue</h3><p>Similarity signals generated by analysis</p></div><button className="text-btn" onClick={() => setSection("integrity")}>Review →</button></div>
            {latestFindings.length ? latestFindings.map((f) => <div className="signal-row" key={f.id}><div className="signal-icon">⌕</div><div className="signal-info"><strong>{f.evidence.matching_question_count ?? "—"} matching responses</strong><small>{f.evidence.comparable_question_count ?? "—"} comparable questions · {f.status.replaceAll("_"," ")}</small></div><div className="score">{Math.round(f.similarity_score * 100)}<small>%</small></div></div>) : <div className="compact-empty">No review leads found. Analysis requires submitted scripts.</div>}
          </section></div>
          <div className="bottom-note"><span>ⓘ</span><p><strong>Fairness guardrail</strong> — The system surfaces patterns for examination by authorized staff. Shared answers alone do not prove cheating, and no automated score may determine a candidate’s result.</p></div>
        </>}
        {section === "examinations" && <div className="workspace-grid"><section className="panel form-panel"><div className="panel-head"><div><h3>Create examination</h3><p>Register an official session record</p></div></div><form className="stack-form" onSubmit={(e) => submitAction(e,"/examinations","POST",(f) => ({code:f.get("code"),title:f.get("title"),level:f.get("level"),subject:f.get("subject"),exam_date:f.get("exam_date")}),"Examination record created.")}><label>Session code<input name="code" required minLength={2} placeholder="PLE-2027-MATH" /></label><label>Examination title<input name="title" required placeholder="Primary Leaving Examination" /></label><div className="form-row"><label>Level<select name="level" required><option value="">Select level</option><option>PLE</option><option>O_LEVEL</option><option>A_LEVEL</option><option>TVET</option></select></label><label>Subject<input name="subject" required placeholder="Mathematics" /></label></div><label>Exam date<input type="date" name="exam_date" required /></label><button className="primary-btn" disabled={busy}>Create session <span>→</span></button></form></section><section className="panel"><div className="panel-head"><div><h3>Registered sessions</h3><p>Live API records · {examinations.length} total</p></div></div><DataTable rows={examinations as unknown as Row[]} columns={["code","title","level","subject","exam_date","status"]} empty="No sessions registered." /></section></div>}
        {section === "candidates" && <div className="workspace-grid"><section className="panel form-panel"><div className="panel-head"><div><h3>Register candidate</h3><p>Link a candidate to a registered examination</p></div></div><form className="stack-form" onSubmit={(e) => submitAction(e,"/candidates","POST",(f) => ({examination_id:f.get("examination_id"),registration_number:f.get("registration_number"),full_name:f.get("full_name"),school_code:f.get("school_code"),centre_code:f.get("centre_code"),room_code:f.get("room_code") || null,seat_number:f.get("seat_number") || null}),"Candidate registered.")}>{examOptions()}<label>Registration number<input name="registration_number" required /></label><label>Candidate full name<input name="full_name" required /></label><div className="form-row"><label>School code<input name="school_code" required /></label><label>Centre code<input name="centre_code" required /></label></div><div className="form-row"><label>Room code<input name="room_code" /></label><label>Seat number<input name="seat_number" /></label></div><button className="primary-btn" disabled={busy || !selectedExam}>Register candidate →</button></form><p className="field-note">Bulk registration imports and source-system reconciliation should be enabled only after the approved NESA/SDMS integration and identity controls are configured.</p></section><section className="panel"><div className="panel-head"><div><h3>Candidate roster lookup</h3><p>Choose an examination and fetch records</p></div></div><form className="inline-form" onSubmit={async (e) => { e.preventDefault(); setBusy(true); try { const result = await request<Row[]>(`/candidates?examination_id=${encodeURIComponent(selectedExam)}`,token); setCandidateRows(result); setMessage(`Loaded ${result.length} candidate record(s). Candidate data is shown only in this session.`); } catch(err) { setError((err as Error).message); } finally { setBusy(false); } }}><button className="outline-btn" disabled={!selectedExam || busy}>Fetch roster</button></form><div style={{marginTop:16}}><DataTable rows={candidateRows} columns={["registration_number","full_name","school_code","centre_code","room_code","seat_number","attendance_status"]} empty="Select an examination and fetch its roster." /></div><div className="bottom-note"><span>⛨</span><p>Candidate identity and results are sensitive data. Use only authorized records and avoid exporting lists to unmanaged devices.</p></div></section></div>}
        {section === "staff" && <div className="workspace-grid"><section className="panel form-panel"><div className="panel-head"><div><h3>Add staff record</h3><p>New records default to not yet eligible</p></div></div><form className="stack-form" onSubmit={(e) => submitAction(e,"/staff","POST",(f) => ({staff_reference:f.get("staff_reference"),full_name:f.get("full_name"),employing_school_code:f.get("employing_school_code")}),"Staff record added; eligibility remains unverified.")}><label>Official staff reference<input name="staff_reference" required /></label><label>Full name<input name="full_name" required /></label><label>Employing school code<input name="employing_school_code" required /></label><button className="primary-btn" disabled={busy}>Add staff record →</button></form><div className="bottom-note"><span>!</span><p>Eligibility must be reviewed from an authoritative staff source before assignment. Records entered here are not independently verified against government systems.</p></div></section><section className="panel"><div className="panel-head"><div><h3>Eligibility control</h3><p>Assignments are rejected until a reviewer sets eligibility</p></div></div><p className="muted">Staff records and eligibility reviews are available through the authenticated API. For controlled changes, use the API operation documented in the OpenAPI reference and provide the review rationale.</p><code className="endpoint">PATCH /staff/{'{staff_id}'}/eligibility?eligible=true&amp;note=...</code></section></div>}
        {section === "custody" && <div className="workspace-grid"><section className="panel form-panel"><div className="panel-head"><div><h3>Register paper batch</h3><p>Create the batch before recording handovers</p></div></div><form className="stack-form" onSubmit={async (e) => { await submitAction(e,"/paper-batches","POST",(f) => ({examination_id:f.get("examination_id"),batch_code:f.get("batch_code"),destination_centre_code:f.get("destination_centre_code"),paper_count:Number(f.get("paper_count")),seal_identifier:f.get("seal_identifier")}),"Paper batch registered."); }}><label>Examination{examOptions()}</label><label>Batch identifier<input name="batch_code" required /></label><label>Destination centre code<input name="destination_centre_code" required /></label><div className="form-row"><label>Paper count<input type="number" min="1" name="paper_count" required /></label><label>Tamper-evident seal ID<input name="seal_identifier" required minLength={4} /></label></div><button className="primary-btn" disabled={busy || !selectedExam}>Register batch →</button></form><p className="field-note">After creation, use the returned batch ID to record SEALED → DISPATCHED → RECEIVED → OPENED → RETURNED → RECONCILED transitions.</p></section><section className="panel"><div className="panel-head"><div><h3>Custody transition rules</h3><p>Out-of-order events are rejected by the API</p></div></div>{["PREPARED · SEALED","SEALED · DISPATCHED","DISPATCHED · RECEIVED","RECEIVED · OPENED","OPENED · RETURNED","RETURNED · RECONCILED"].map((s,i)=><div className="timeline-row" key={s}><span>{String(i+1).padStart(2,"0")}</span><strong>{s.split(" · ")[1]}</strong><small>{s.split(" · ")[0]} →</small></div>)}<p className="muted small-copy">Each recorded event is linked by a SHA-256 hash and also recorded in the platform audit trail. A live service should anchor periodic hashes in independently managed immutable storage.</p></section></div>}
        {section === "integrity" && <div className="panel"><div className="panel-head"><div><h3>Answer-pattern analysis</h3><p>Compare submitted response patterns across an examination cohort</p></div></div><form className="analysis-launch" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setError(""); try { const result = await request<{scripts_analyzed:number;new_review_leads:number;decision_policy:string}>(`/integrity/analyze/${encodeURIComponent(selectedExam)}`,token,{method:"POST"}); setMessage(`Analysis processed ${result.scripts_analyzed} scripts and created ${result.new_review_leads} new review lead(s). ${result.decision_policy}`); await load(token); } catch(err) { setError((err as Error).message); } finally { setBusy(false); } }}><div className="analysis-copy"><span className="analysis-icon">⌕</span><div><strong>Run cohort analysis</strong><p>Select an examination with at least two ingested answer scripts. Similarity results are triage leads only.</p></div></div>{examOptions()}<button className="primary-btn" disabled={busy || !selectedExam}>Run analysis →</button></form><div className="panel-head section-subhead"><div><h3>Review leads</h3><p>Model { "answer-pattern-v1.0.0" } · No automated guilt decisions</p></div></div><DataTable rows={findings as unknown as Row[]} columns={["id","similarity_score","model_version","status","created_at"]} empty="No findings to review. Ingest scripts and run an analysis first." />{findings.length > 0 && <p className="field-note">Each finding includes comparison counts, matched question identifiers and limitations in the API response. Review original scripts and context before opening a case.</p>}</div>}
        {section === "cases" && <div className="panel"><div className="panel-head"><div><h3>Investigation cases</h3><p>Independent review required before a decision is recorded</p></div></div><div className="case-create"><form className="stack-form" onSubmit={(e) => submitAction(e,`/cases/from-finding/${(new FormData(e.currentTarget)).get("finding_id")}`,"POST",(f) => ({affected_candidate_id:f.get("affected_candidate_id")}),"Case opened for human investigation.")}><label>Finding ID<select name="finding_id" required defaultValue=""><option value="">Select a finding…</option>{findings.map((f) => <option key={f.id} value={f.id}>{f.id.slice(0,8)} · {Math.round(f.similarity_score*100)}% similarity</option>)}</select></label><label>Affected candidate ID<input name="affected_candidate_id" required /></label><button className="primary-btn" disabled={busy || !findings.length}>Open case →</button></form><div className="bottom-note"><span>⛨</span><p>Investigator and decision-maker must be different accounts. Decisions require a written evidence summary, and the appeal path also enforces separate decision-makers.</p></div></div><div className="panel-head section-subhead"><div><h3>Case register</h3><p>{cases.length} case record(s)</p></div></div><DataTable rows={cases as unknown as Row[]} columns={["id","finding_id","affected_candidate_id","status","outcome","created_at"]} empty="No investigation cases have been opened." /></div>}
        {section === "audit" && <div className="panel"><div className="panel-head"><div><h3>Audit-chain health</h3><p>Hash-link verification of recorded application events</p></div><button className="outline-btn" onClick={async () => { try { const result = await request<Row>("/audit/status",token); setAudit(result); setMessage("Audit status refreshed."); } catch(err) { setError((err as Error).message); } }}>Check integrity ↻</button></div>{audit ? <><div className="audit-summary"><div className="audit-symbol">{audit.valid === true ? "✓" : "!"}</div><div><span className="eyebrow">CHAIN LINK STATUS</span><h2>{audit.valid === true ? "No broken links detected" : "Review required"}</h2><p>{String(audit.note ?? "Access limited or status unavailable.")}</p></div></div><div className="metric-grid audit-metrics"><div className="metric-card"><div className="metric-top"><span>Recorded events</span></div><strong>{String(audit.event_count ?? "—")}</strong></div><div className="metric-card"><div className="metric-top"><span>Linkage status</span></div><strong>{audit.valid === true ? "Valid" : "Not verified"}</strong></div></div><label className="hash-label">Current head hash</label><code className="hash-value">{String(audit.head_hash ?? "Unavailable")}</code></> : <div className="empty-state"><strong>Audit status unavailable</strong><p>The account may not have audit permission, or the API is not available.</p></div>}<div className="bottom-note"><span>ⓘ</span><p>Current verification checks hash-link continuity. It does not independently prove that a privileged database administrator could not rewrite history. Production must anchor hashes externally and test the verification job independently.</p></div></div>}
        <footer className="app-footer"><span>REI · Secure examination operations</span><span>All times and audit events are subject to official system configuration</span></footer>
      </div>
    </main>
  </div>;
}
