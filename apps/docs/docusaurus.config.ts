import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'RemediAI',
  tagline: 'AI-powered exception analysis and remediation for enterprise .NET applications on Azure.',
  favicon: 'img/favicon.ico',

  url: 'https://akeesari.github.io',
  baseUrl: '/remediai/',

  organizationName: 'akeesari',
  projectName: 'remediai',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  themes: ['@docusaurus/theme-mermaid'],

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  plugins: [
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: true,
        language: ['en'],
        docsRouteBasePath: '/docs',
        indexDocs: true,
        indexBlog: true,
        indexPages: true,
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/akeesari/remediai/tree/main/apps/docs/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          editUrl: 'https://github.com/akeesari/remediai/tree/main/apps/docs/',
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
        sitemap: {
          changefreq: 'weekly',
          priority: 0.5,
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/social-card.png',
    metadata: [
      {
        name: 'description',
        content:
          'RemediAI is an AI-powered exception analysis and remediation platform for enterprise .NET applications on Azure. Automate triage, root cause analysis, and Azure DevOps Bug creation with a LangGraph multi-agent pipeline.',
      },
      { property: 'og:type', content: 'website' },
      { property: 'og:title', content: 'RemediAI — AI-Powered Exception Remediation' },
      {
        property: 'og:description',
        content:
          'Detect, analyze, and remediate .NET application exceptions with AI agents. Automated triage, root cause analysis, and Azure DevOps Bug creation.',
      },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: 'RemediAI — AI-Powered Exception Remediation' },
    ],
    colorMode: {
      defaultMode: 'light',
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },
    announcementBar: {
      id: 'early_access',
      content:
        'RemediAI is in active development — phases 1–21 complete. <a href="/remediai/docs/roadmap">View the roadmap</a>.',
      backgroundColor: '#0078D4',
      textColor: '#ffffff',
      isCloseable: true,
    },
    navbar: {
      title: 'RemediAI',
      logo: {
        alt: 'RemediAI Logo',
        src: 'img/logo.svg',
        srcDark: 'img/logo-dark.svg',
      },
      items: [
        {
          to: '/',
          label: 'Home',
          position: 'left',
        },
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        { to: '/blog', label: 'Blog', position: 'left' },
        { to: '/docs/roadmap', label: 'Roadmap', position: 'left' },
        {
          href: 'https://github.com/akeesari/remediai',
          position: 'right',
          className: 'header-github-link',
          'aria-label': 'GitHub repository',
        },
      ],
      hideOnScroll: false,
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            { label: 'Introduction', to: '/docs/intro' },
            { label: 'Getting Started', to: '/docs/getting-started/prereqs' },
            { label: 'Architecture', to: '/docs/architecture/overview' },
            { label: 'Agent Pipeline', to: '/docs/agents/pipeline' },
            { label: 'API Reference', to: '/docs/api' },
          ],
        },
        {
          title: 'Integrations',
          items: [
            { label: 'Azure Monitor', to: '/docs/integrations/azure-monitor' },
            { label: 'Azure DevOps', to: '/docs/integrations/azure-devops' },
            { label: 'Azure OpenAI', to: '/docs/integrations/azure-openai' },
            { label: 'Azure AI Search', to: '/docs/integrations/azure-ai-search' },
            { label: 'Azure Key Vault', to: '/docs/integrations/azure-key-vault' },
          ],
        },
        {
          title: 'Project',
          items: [
            { label: 'Roadmap', to: '/docs/roadmap' },
            { label: 'Contributing', to: '/docs/contributing/dev-environment' },
            { label: 'Security', to: '/docs/security/principles' },
            { label: 'Blog', to: '/blog' },
            {
              label: 'GitHub',
              href: 'https://github.com/akeesari/remediai',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} RemediAI Contributors. Licensed under <a href="https://github.com/akeesari/remediai/blob/main/LICENSE" target="_blank" rel="noopener noreferrer">Apache 2.0</a>.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'bash', 'yaml', 'json', 'typescript', 'csharp', 'sql'],
    },
    mermaid: {
      theme: { light: 'neutral', dark: 'dark' },
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
