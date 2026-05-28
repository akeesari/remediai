import React, { useEffect } from 'react';
import useIsBrowser from '@docusaurus/useIsBrowser';

export default function Root({ children }: { children: React.ReactNode }): React.JSX.Element {
  const isBrowser = useIsBrowser();

  useEffect(() => {
    if (!isBrowser) return;

    // Add mobile docs sidebar toggle functionality
    const handleDocsSidebarToggle = () => {
      const sidebar = document.querySelector('.theme-doc-sidebar-container');
      if (sidebar) {
        const isHidden = sidebar.getAttribute('data-hidden') !== 'false';
        sidebar.setAttribute('data-hidden', isHidden ? 'false' : 'true');
        document.documentElement.setAttribute('data-sidebar-open', isHidden ? 'true' : 'false');
      }
    };

    // Create sub-header for docs pages on mobile
    const createDocsSidebarToggle = () => {
      const docsSidebar = document.querySelector('.theme-doc-sidebar-container');
      if (!docsSidebar) {
        // If not on a docs page, remove the sub-header if it exists
        const existingHeader = document.querySelector('.docs-mobile-sub-header');
        if (existingHeader) existingHeader.remove();
        return;
      }

      // Check if sub-header already exists
      let subHeader = document.querySelector('.docs-mobile-sub-header');
      
      // Extract active category/page title from breadcrumbs if available
      let activeTitle = 'Documentation';
      const breadcrumbs = document.querySelectorAll('.breadcrumbs__item');
      if (breadcrumbs.length > 0) {
        const lastItem = breadcrumbs[breadcrumbs.length - 1];
        if (lastItem) {
          activeTitle = lastItem.textContent?.trim() || 'Documentation';
        }
      }

      if (!subHeader) {
        const mainElement = document.querySelector('main');
        if (!mainElement) return;

        subHeader = document.createElement('div');
        subHeader.className = 'docs-mobile-sub-header';

        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'docs-mobile-sidebar-toggle';
        toggleBtn.setAttribute('aria-label', 'Toggle docs sidebar');
        toggleBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="4" y1="6" x2="20" y2="6"></line>
            <line x1="4" y1="12" x2="20" y2="12"></line>
            <line x1="4" y1="18" x2="20" y2="18"></line>
          </svg>
          <span>Doc Sections</span>
        `;
        toggleBtn.onclick = (e) => {
          e.stopPropagation();
          handleDocsSidebarToggle();
        };

        const titleSpan = document.createElement('span');
        titleSpan.className = 'docs-mobile-sub-header-title';
        titleSpan.innerText = activeTitle;

        subHeader.appendChild(toggleBtn);
        subHeader.appendChild(titleSpan);

        mainElement.insertBefore(subHeader, mainElement.firstChild);
      } else {
        // Update the title if it has changed
        const titleSpan = subHeader.querySelector('.docs-mobile-sub-header-title');
        if (titleSpan && titleSpan.textContent !== activeTitle) {
          titleSpan.textContent = activeTitle;
        }
      }
    };

    // Close sidebar when clicking backdrop
    const handleBackdropClick = (e: MouseEvent) => {
      const sidebar = document.querySelector('.theme-doc-sidebar-container');
      const toggle = document.querySelector('.docs-mobile-sidebar-toggle');
      
      if (
        sidebar &&
        sidebar.getAttribute('data-hidden') === 'false' &&
        !sidebar.contains(e.target as Node) &&
        !toggle?.contains(e.target as Node)
      ) {
        sidebar.setAttribute('data-hidden', 'true');
        document.documentElement.setAttribute('data-sidebar-open', 'false');
      }
    };

    // Initialize
    createDocsSidebarToggle();
    document.addEventListener('click', handleBackdropClick);

    // Re-create/update sub-header on navigation or DOM mutations
    const observer = new MutationObserver(() => {
      createDocsSidebarToggle();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    // Cleanup
    return () => {
      document.removeEventListener('click', handleBackdropClick);
      observer.disconnect();
      const header = document.querySelector('.docs-mobile-sub-header');
      if (header) header.remove();
    };
  }, [isBrowser]);

  return <>{children}</>;
}
