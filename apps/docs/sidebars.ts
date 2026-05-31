import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'doc',
      id: 'intro',
      label: 'Introduction',
    },
    {
      type: 'category',
      label: 'Getting Started',
      collapsed: false,
      items: [
        'getting-started/prereqs',
        'getting-started/installation',
        'getting-started/first-incident',
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/data-flow',
        'architecture/data-model',
        'architecture/tech-stack',
      ],
    },
    {
      type: 'category',
      label: 'Agent Pipeline',
      items: [
        'agents/pipeline',
        'agents/triage',
        'agents/root-cause',
        'agents/code-context',
        'agents/rag-retrieval',
        'agents/fix-planner',
        'agents/validation',
        'agents/pr-agent',
      ],
    },
    {
      type: 'category',
      label: 'Integrations',
      items: [
        'integrations/azure-monitor',
        'integrations/azure-devops',
        'integrations/azure-openai',
        'integrations/azure-ai-search',
        'integrations/azure-key-vault',
      ],
    },
    {
      type: 'doc',
      id: 'configuration',
      label: 'Configuration Reference',
    },
    {
      type: 'category',
      label: 'Security',
      items: [
        'security/principles',
        'security/pii-scrubbing',
        'security/identity',
        'security/audit-log',
      ],
    },
    {
      type: 'doc',
      id: 'api',
      label: 'API Reference',
    },
    {
      type: 'category',
      label: 'Contributing',
      items: [
        'contributing/dev-environment',
        'contributing/branch-conventions',
        'contributing/phase-workflow',
      ],
    },
  ],
};

export default sidebars;
