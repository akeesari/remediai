import React, { useEffect, useState } from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import clsx from 'clsx';

/* ─── Feature grid data ─── */
const features = [
  {
    icon: '🔍',
    title: 'Intelligent Log Ingestion',
    body: 'Connects to Azure Monitor and Application Insights via KQL queries. Automatically deduplicates exceptions by fingerprint hash and publishes incidents to Azure Service Bus.',
  },
  {
    icon: '🎯',
    title: 'AI Triage',
    body: 'Assigns priority (critical / high / medium / low) and semantic labels. Detects known patterns — null references, timeouts, auth failures — and groups related incidents automatically.',
  },
  {
    icon: '🧠',
    title: 'Root Cause Analysis',
    body: 'Parses the stack trace, identifies the faulty component, and produces a structured JSON root cause summary with confidence score. Every reasoning step is recorded for auditability.',
  },
  {
    icon: '📂',
    title: 'Code Context',
    body: 'Retrieves the exact source files and line ranges referenced in the stack trace from Azure DevOps Repos. Skips third-party packages and limits to the 5 most relevant snippets.',
  },
  {
    icon: '📚',
    title: 'RAG Retrieval',
    body: 'Runs a hybrid vector + keyword search over Azure AI Search. Prioritises runbooks, prior fixes, and documentation to ground every recommendation in real context.',
  },
  {
    icon: '🛠️',
    title: 'Fix Recommendations',
    body: 'Generates a ranked list of up to 3 remediation options — each with a description, target files, suggested change, confidence score, and source references.',
  },
  {
    icon: '🐛',
    title: 'Azure DevOps Bug Creation',
    body: 'Automatically creates a fully-populated Bug work item in Azure DevOps Boards with root cause, repro steps, and a direct link back to the incident record.',
  },
  {
    icon: '🔀',
    title: 'Draft PR Generation',
    body: 'After a human approves a recommendation in the dashboard, the PR Agent creates a branch, applies the patch, and opens a draft pull request — never auto-merges.',
  },
  {
    icon: '📊',
    title: 'React Dashboard',
    body: 'A clean, filterable incident list with status badges, a full detail view showing root cause and recommendations, and a metrics panel tracking volume and MTTT.',
  },
];

/* ─── How it works steps ─── */
const workflowSteps = [
  'Exception appears in Application Insights.',
  'KQL query ingests and deduplicates the exception.',
  'Incident published to Azure Service Bus.',
  'LangGraph worker picks up the incident.',
  'Triage Agent assigns priority and groups incidents.',
  'Root Cause Agent analyzes the stack trace.',
  'Code Context Agent retrieves relevant source files.',
  'RAG Agent fetches runbooks and prior fixes.',
  'Fix Planner produces ranked recommendations.',
  'Azure DevOps Bug created with full context.',
  'Human approves a recommendation in the dashboard.',
  'PR Agent creates a draft pull request for review.',
];

/* ─── Technology badges ─── */
const techStack = [
  { label: 'Python 3.12', icon: 'python', color: 'blue' },
  { label: 'FastAPI', icon: 'fastapi', color: 'teal' },
  { label: 'LangGraph', icon: 'langgraph', color: 'purple' },
  { label: 'Azure OpenAI GPT-4o', icon: 'openai', color: 'green' },
  { label: 'Azure AI Search', icon: 'azure-search', color: 'cyan' },
  { label: 'Azure Monitor', icon: 'azure-monitor', color: 'orange' },
  { label: 'Azure Service Bus', icon: 'azure-bus', color: 'indigo' },
  { label: 'PostgreSQL 16', icon: 'postgresql', color: 'blue' },
  { label: 'React 18', icon: 'react', color: 'cyan' },
  { label: 'TypeScript', icon: 'typescript', color: 'blue' },
  { label: 'Azure DevOps', icon: 'azure-devops', color: 'blue' },
  { label: 'AKS', icon: 'kubernetes', color: 'blue' },
  { label: 'Terraform', icon: 'terraform', color: 'purple' },
  { label: 'Helm', icon: 'helm', color: 'cyan' },
];

/* ─── Security pillars ─── */
const securityPillars = [
  {
    icon: '👥',
    step: 'PRINCIPLE 1',
    title: 'Humans in the Loop',
    body: 'Every code change requires an explicit human approval. Recommendations are surfaced, never auto-applied.',
    color: 'cyan',
  },
  {
    icon: '🚫',
    step: 'PRINCIPLE 2',
    title: 'No Auto-Merge',
    body: 'PRs are always created as drafts. RemediAI never sets auto-complete or merges directly to any branch.',
    color: 'orange',
  },
  {
    icon: '🔒',
    step: 'PRINCIPLE 3',
    title: 'PII Scrubbed',
    body: 'Emails, IPs, and user identifiers are stripped from every exception payload before transmission to any AI endpoint.',
    color: 'purple',
  },
  {
    icon: '📝',
    step: 'PRINCIPLE 4',
    title: 'Full Audit Trail',
    body: 'Every agent decision is recorded in an immutable audit log table — what ran, what it decided, and why.',
    color: 'green',
  },
];

export default function Home(): React.JSX.Element {
  const { siteConfig } = useDocusaurusContext();
  const [activeFeature, setActiveFeature] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveFeature((prev) => (prev + 1) % 3);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Layout
      title={siteConfig.title}
      description={siteConfig.tagline}
    >
      {/* ── Hero ── */}
      <header className="hero-modern">
        <div className="hero-glow hero-glow-1"></div>
        <div className="hero-glow hero-glow-2"></div>
        <div className="hero-pattern"></div>
        
        <div className="container hero-content">
          <div className="pill-badge fade-up">
            <span className="pill-dot"></span>
            <span>Phases 1–21 complete · v0.4 in active development</span>
          </div>
          
          <h1 className="hero-title fade-up-1">
            Stop finding bugs.<br />
            <span className="hero-title-gradient">Start fixing them.</span>
          </h1>
          
          <p className="hero-subtitle fade-up-2">
            RemediAI is an AI-powered exception analysis and remediation platform for enterprise
            .NET applications on Azure. From Application Insights alert to Azure DevOps Bug in
            under 3 minutes — with full root cause analysis and fix recommendations.
          </p>
          
          <div className="hero-cta-group fade-up-3">
            <Link to="/docs/getting-started/prereqs" className="btn-modern btn-primary">
              Get started
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </Link>
            <Link to="https://github.com/akeesari/remediai" className="btn-modern btn-secondary">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              Star on GitHub
            </Link>
          </div>
          
          <p className="hero-meta fade-up-3">
            Set up in 15 minutes · Works with Azure · Enterprise-ready
          </p>
        </div>
      </header>

      {/* ── Stats Bar (Clean Style) ── */}
      <section className="stats-bar">
        <div className="container">
          <div className="stats-bar-grid">
            <div className="stat-item-clean">
              <div className="stat-value">8</div>
              <div className="stat-label-clean">AI agents</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item-clean">
              <div className="stat-value">21</div>
              <div className="stat-label-clean">phases complete</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item-clean">
              <div className="stat-value">&lt; 3 min</div>
              <div className="stat-label-clean">triage time</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item-clean">
              <div className="stat-value">500/hr</div>
              <div className="stat-label-clean">incident throughput</div>
            </div>
          </div>
        </div>
      </section>

      <main>
        {/* ── Problem / Solution (Apple Style) ── */}
        <section className="section-modern">
          <div className="container">
            <div className="section-header-modern">
              <span className="section-eyebrow">The Challenge</span>
              <h2 className="section-title-modern">Stop wasting time on manual triage</h2>
              <p className="section-lead-modern">
                Your engineering team shouldn't spend hours hunting down exceptions. 
                RemediAI automates the entire investigation pipeline so you can focus on what matters — shipping features.
              </p>
            </div>
            <div className="apple-cards-grid">
              <div className="apple-card apple-card-problem">
                <div className="apple-card-header">
                  <div className="apple-card-icon apple-card-icon-problem">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/>
                      <line x1="12" y1="8" x2="12" y2="12"/>
                      <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                  </div>
                  <h3 className="apple-card-title">Without RemediAI</h3>
                </div>
                <div className="apple-card-content">
                  <ul className="apple-list">
                    <li>Alert fires at 2 AM — someone gets paged</li>
                    <li>Engineer manually searches Application Insights</li>
                    <li>Checks multiple dashboards to correlate the exception</li>
                    <li>Reads stack trace and guesses root cause</li>
                    <li>Creates ticket by hand with incomplete context</li>
                    <li>Searches codebase for relevant files</li>
                    <li>Writes reproduction steps from memory</li>
                    <li>Repeats for every recurring exception</li>
                  </ul>
                </div>
                <div className="apple-card-footer">
                  <span className="apple-card-metric">Hours wasted per incident</span>
                </div>
              </div>

              <div className="apple-card apple-card-solution">
                <div className="apple-card-header">
                  <div className="apple-card-icon apple-card-icon-solution">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                      <polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                  </div>
                  <h3 className="apple-card-title">With RemediAI</h3>
                </div>
                <div className="apple-card-content">
                  <ul className="apple-list">
                    <li>Exception detected automatically in Application Insights</li>
                    <li>Deduplicated — no duplicate incidents for same error</li>
                    <li>AI Triage Agent assigns priority and groups events</li>
                    <li>Root Cause Agent produces structured analysis</li>
                    <li>Azure DevOps Bug created with full context</li>
                    <li>Code Context Agent finds exact lines in your repo</li>
                    <li>Fix Planner ranks remediation options with confidence</li>
                    <li>Engineer reviews and decides in minutes, not hours</li>
                  </ul>
                </div>
                <div className="apple-card-footer">
                  <span className="apple-card-metric">Under 3 minutes to triage</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Feature Grid ── */}
        <section className="section-modern section-alt">
          <div className="container">
            <div className="section-header-modern">
              <span className="section-eyebrow">Capabilities</span>
              <h2 className="section-title-modern">Everything you need. Nothing you don't.</h2>
              <p className="section-lead-modern">
                A complete agentic pipeline from log ingestion through to draft pull request —
                with humans in control at every decision point.
              </p>
            </div>
            <div className="features-grid-modern">
              {features.map((f, i) => (
                <div key={f.title} className="feature-card-modern" style={{ animationDelay: `${i * 0.05}s` }}>
                  <div className="feature-icon-modern">{f.icon}</div>
                  <h3 className="feature-title-modern">{f.title}</h3>
                  <p className="feature-body-modern">{f.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Architecture diagram ── */}
        <section className="section-modern">
          <div className="container">
            <div className="section-header-modern">
              <span className="section-eyebrow">Architecture</span>
              <h2 className="section-title-modern">Cloud-native on Azure, end to end</h2>
              <p className="section-lead-modern">
                Independently deployable services on AKS, communicating via Azure Service Bus,
                with Workload Identity for zero-credential authentication.
              </p>
            </div>
            <div className="architecture-card">
              <div className="architecture-header">
                <div className="window-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="architecture-title">System Architecture</span>
              </div>
              <div className="architecture-diagram">
                <div className="arch-line">
                  <span className="arch-component workload">Application Workloads</span>
                  <span className="arch-detail">(AKS / App Service / VMs)</span>
                </div>
                <div className="arch-arrow">│</div>
                <div className="arch-arrow">▼</div>
                <div className="arch-line">
                  <span className="arch-component monitor">Application Insights / Azure Monitor</span>
                  <span className="arch-arrow">◄────</span>
                  <span className="arch-detail">KQL queries (every N mins)</span>
                </div>
                <div className="arch-arrow">│</div>
                <div className="arch-arrow">▼</div>
                <div className="arch-line">
                  <span className="arch-component ingestion">Log Ingestion Service</span>
                  <span className="arch-detail">(Python · AKS)</span>
                </div>
                <div className="arch-line arch-indent">
                  <span className="arch-arrow">│</span>
                  <span className="arch-detail">fingerprint + dedup</span>
                </div>
                <div className="arch-arrow">▼</div>
                <div className="arch-line">
                  <span className="arch-component bus">Azure Service Bus</span>
                  <span className="arch-arrow">────</span>
                  <span className="arch-detail">incident-events topic</span>
                </div>
                <div className="arch-arrow">│</div>
                <div className="arch-arrow">▼</div>
                <div className="arch-line">
                  <span className="arch-component agent">Agent Worker</span>
                  <span className="arch-detail">(Python + LangGraph)</span>
                </div>
                <div className="arch-line arch-indent">
                  <span className="arch-arrow">├──</span>
                  <span className="arch-component ai">Azure OpenAI GPT-4o</span>
                  <span className="arch-detail">(Triage / Root Cause / Fix Planner)</span>
                </div>
                <div className="arch-line arch-indent">
                  <span className="arch-arrow">├──</span>
                  <span className="arch-component devops">Azure DevOps Repos</span>
                  <span className="arch-detail">(Code Context)</span>
                </div>
                <div className="arch-line arch-indent">
                  <span className="arch-arrow">├──</span>
                  <span className="arch-component search">Azure AI Search</span>
                  <span className="arch-detail">(RAG Retrieval)</span>
                </div>
                <div className="arch-line arch-indent">
                  <span className="arch-arrow">├──</span>
                  <span className="arch-component devops">Azure DevOps Boards</span>
                  <span className="arch-detail">(Bug Creation)</span>
                </div>
                <div className="arch-line arch-indent">
                  <span className="arch-arrow">└──</span>
                  <span className="arch-component db">PostgreSQL / Blob Storage</span>
                  <span className="arch-detail">(Persistence)</span>
                </div>
                <div className="arch-arrow">│</div>
                <div className="arch-arrow">▼</div>
                <div className="arch-line">
                  <span className="arch-component api">FastAPI Backend API</span>
                  <span className="arch-arrow">◄───</span>
                  <span className="arch-component cache">Redis cache</span>
                </div>
                <div className="arch-arrow">│</div>
                <div className="arch-arrow">▼</div>
                <div className="arch-line">
                  <span className="arch-component dashboard">React Dashboard</span>
                  <span className="arch-arrow">────</span>
                  <span className="arch-detail">Incidents · Analyses · Metrics · Approvals</span>
                </div>
                <div className="arch-spacer"></div>
                <div className="arch-line">
                  <span className="arch-component vault">Azure Key Vault</span>
                  <span className="arch-arrow">────</span>
                  <span className="arch-detail">secrets</span>
                  <span className="arch-arrow">──►</span>
                  <span className="arch-detail">all services</span>
                </div>
                <div className="arch-line">
                  <span className="arch-component identity">Managed Identity</span>
                  <span className="arch-arrow">──────────────►</span>
                  <span className="arch-component vault">Key Vault</span>
                </div>
              </div>
            </div>
            <div style={{ textAlign: 'center', marginTop: '2rem' }}>
              <Link to="/docs/architecture/overview" className="btn-modern btn-secondary">
                Read the full architecture
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </Link>
            </div>
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="section-modern section-alt">
          <div className="container">
            <div className="section-header-modern">
              <span className="section-eyebrow">How It Works</span>
              <h2 className="section-title-modern">Exception to Azure DevOps Bug in 12 steps</h2>
              <p className="section-lead-modern">
                The full pipeline from detection to a draft pull request, with a human approval gate before any code is touched.
              </p>
            </div>
            <div className="workflow-grid">
              {workflowSteps.map((step, i) => (
                <div key={i} className="workflow-card">
                  <div className="workflow-number">{i + 1}</div>
                  <div className="workflow-text">{step}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Technology stack ── */}
        <section className="section-modern">
          <div className="container">
            <div className="section-header-modern">
              <span className="section-eyebrow">Technology Stack</span>
              <h2 className="section-title-modern">Built on the Azure ecosystem</h2>
              <p className="section-lead-modern">
                Python + LangGraph backend, React frontend, and deep Azure-native integration throughout.
              </p>
            </div>
            <div className="tech-grid">
              {techStack.map((t, i) => (
                <div key={t.label} className={`tech-badge-modern tech-badge-${t.color}`} style={{ animationDelay: `${i * 0.03}s` }}>
                  <span className={`tech-icon tech-icon-${t.icon}`}></span>
                  <span className="tech-label">{t.label}</span>
                </div>
              ))}
            </div>
            <div style={{ textAlign: 'center', marginTop: '2.5rem' }}>
              <Link to="/docs/architecture/tech-stack" className="link-modern">
                View full stack with rationale →
              </Link>
            </div>
          </div>
        </section>

        {/* ── Security promise ── */}
        <section className="section-modern section-alt">
          <div className="container">
            <div className="section-header-modern">
              <span className="section-eyebrow">Security</span>
              <h2 className="section-title-modern">Safe by design — not as an afterthought</h2>
              <p className="section-lead-modern">
                RemediAI operates on a zero-trust, human-in-the-loop model. Agents have read-only access by default.
              </p>
            </div>
            <div className="security-grid-modern">
              {securityPillars.map((p, i) => (
                <div key={p.title} className={`security-card-modern security-card-${p.color}`} style={{ animationDelay: `${i * 0.1}s` }}>
                  <div className={`security-icon-container security-icon-${p.color}`}>
                    <span className="security-icon-modern">{p.icon}</span>
                  </div>
                  <div className="security-step">{p.step}</div>
                  <h3 className="security-title-modern">{p.title}</h3>
                  <p className="security-body-modern">{p.body}</p>
                </div>
              ))}
            </div>
            <div style={{ textAlign: 'center', marginTop: '2.5rem' }}>
              <Link to="/docs/security/principles" className="link-modern">
                Read the security guardrails →
              </Link>
            </div>
          </div>
        </section>

        {/* ── CTA ── */}
        <section className="section-modern">
          <div className="container">
            <div className="cta-modern">
              <div className="cta-glow"></div>
              <h2>Ready to stop triaging by hand?</h2>
              <p>
                Deploy RemediAI on your Azure subscription, connect Application Insights, and watch
                exceptions become triaged incidents in minutes.
              </p>
              <div className="cta-buttons">
                <Link to="/docs/getting-started/prereqs" className="btn-modern btn-primary">
                  Get started
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </Link>
                <Link to="https://github.com/akeesari/remediai" className="btn-modern btn-secondary">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                  Star on GitHub
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
