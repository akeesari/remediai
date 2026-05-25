---
id: intro
title: What is RemediAI?
sidebar_label: Introduction
slug: /intro
---

# What is RemediAI?

RemediAI is an **AI-powered exception analysis and remediation platform** for enterprise .NET applications hosted on Azure. It ingests application exceptions from Azure Monitor / Application Insights, runs a multi-agent analysis pipeline, creates Azure DevOps Bugs, and — after a human approves — generates draft pull requests for review.

---

## The problem it solves

Modern distributed applications running on AKS, App Service, or Azure VMs generate a constant stream of exceptions. Engineering teams spend hours every week:

- Manually searching Application Insights for new errors
- Correlating exceptions across multiple services
- Triaging duplicates and prioritising by severity
- Writing Azure DevOps Bug tickets from scratch
- Hunting through the codebase to find the relevant file

RemediAI automates every step of this investigation so engineers focus on **fixing**, not finding.

---

## How it works

```
1.  Exception appears in Application Insights.
2.  KQL query ingests and deduplicates it.
3.  Incident published to Azure Service Bus.
4.  LangGraph worker picks up the incident.
5.  Triage Agent assigns priority and groups related incidents.
6.  Root Cause Agent analyzes the stack trace.
7.  Code Context Agent retrieves relevant source files.
8.  RAG Agent fetches runbooks and prior fixes.
9.  Fix Planner produces ranked recommendations.
10. Azure DevOps Bug created with full context.
11. Human approves a recommendation in the dashboard.
12. PR Agent creates a draft pull request for review.
```

---

## Key capabilities

| Capability | Description |
|------------|-------------|
| **Log ingestion** | Polls Application Insights via KQL; deduplicates by fingerprint hash |
| **AI triage** | Priority assignment, semantic labeling, incident grouping |
| **Root cause analysis** | Structured JSON output with confidence score and reasoning audit |
| **Code context** | Fetches exact source lines from Azure DevOps Repos |
| **RAG retrieval** | Hybrid vector + keyword search over runbooks, docs, prior fixes |
| **Fix recommendations** | Ranked list with target files, suggested changes, confidence |
| **Bug creation** | Fully-populated Azure DevOps Bug, auto-linked to the incident |
| **Draft PR** | Branch + patch + PR — after human approval, never auto-merge |
| **React dashboard** | Incident list, detail view, metrics panel, approval workflow |

---

## Who uses it

| Role | How RemediAI helps |
|------|--------------------|
| **Platform Engineer** | Connect Azure resources, configure integrations, manage deployments |
| **Developer** | Review incidents, approve recommendations, merge PRs on their schedule |
| **Engineering Lead** | Monitor MTTT trends, set triage policies, track resolution rates |
| **Auditor** | Review the immutable audit log for every agent decision |

---

## What RemediAI does NOT do

- Auto-merge pull requests — humans always approve first.
- Modify production systems directly.
- Process Java, Node.js, or Python application exceptions (MVP is .NET only).
- Integrate with Jira, Grafana, or Datadog (Azure-native only in MVP).
- Provide self-healing automation without human approval.

---

## Next steps

- [Prerequisites](./getting-started/prereqs) — what you need before deploying RemediAI
- [Installation](./getting-started/installation) — connect your Azure tenant and deploy RemediAI
- [Architecture Overview](./architecture/overview) — component diagram and service breakdown
- [Agent Pipeline](./agents/pipeline) — how the multi-agent workflow processes exceptions
