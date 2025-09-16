// FXML4 Documentation JavaScript Enhancements

// Initialize Mermaid diagrams
document$.subscribe(() => {
    mermaid.initialize({
        startOnLoad: true,
        theme: 'neutral',
        themeVariables: {
            primaryColor: '#6B46C1',
            primaryTextColor: '#fff',
            primaryBorderColor: '#7C3AED',
            lineColor: '#5B21B6',
            secondaryColor: '#EDE9FE',
            tertiaryColor: '#F3F4F6'
        }
    });
    mermaid.contentLoaded();
});

// Add copy button to code blocks
document$.subscribe(() => {
    const codeBlocks = document.querySelectorAll('pre > code');

    codeBlocks.forEach((codeBlock) => {
        const button = document.createElement('button');
        button.className = 'md-clipboard md-icon';
        button.title = 'Copy to clipboard';

        const pre = codeBlock.parentNode;
        pre.style.position = 'relative';
        pre.appendChild(button);

        button.addEventListener('click', () => {
            navigator.clipboard.writeText(codeBlock.textContent).then(() => {
                button.classList.add('copied');
                setTimeout(() => button.classList.remove('copied'), 2000);
            });
        });
    });
});

// Add anchor links to headers
document$.subscribe(() => {
    const headers = document.querySelectorAll('h2[id], h3[id], h4[id]');

    headers.forEach((header) => {
        const anchor = document.createElement('a');
        anchor.className = 'headerlink';
        anchor.href = `#${header.id}`;
        anchor.innerHTML = '¶';
        anchor.title = 'Permanent link';
        header.appendChild(anchor);
    });
});

// Enhance tables with sorting
document$.subscribe(() => {
    const tables = document.querySelectorAll('table');

    tables.forEach((table) => {
        const headers = table.querySelectorAll('th');

        headers.forEach((header, index) => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => {
                sortTable(table, index);
            });
        });
    });
});

function sortTable(table, column) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    const sortedRows = rows.sort((a, b) => {
        const aText = a.cells[column].textContent.trim();
        const bText = b.cells[column].textContent.trim();

        // Try to parse as numbers first
        const aNum = parseFloat(aText);
        const bNum = parseFloat(bText);

        if (!isNaN(aNum) && !isNaN(bNum)) {
            return aNum - bNum;
        }

        return aText.localeCompare(bText);
    });

    // Toggle sort direction
    if (table.dataset.sortColumn == column && table.dataset.sortDirection === 'asc') {
        sortedRows.reverse();
        table.dataset.sortDirection = 'desc';
    } else {
        table.dataset.sortColumn = column;
        table.dataset.sortDirection = 'asc';
    }

    // Re-append sorted rows
    sortedRows.forEach(row => tbody.appendChild(row));
}

// Add search highlighting
document$.subscribe(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const query = searchParams.get('q');

    if (query) {
        highlightSearchTerms(query);
    }
});

function highlightSearchTerms(query) {
    const content = document.querySelector('.md-content');
    const terms = query.split(/\s+/);

    terms.forEach(term => {
        if (term.length > 2) {
            const regex = new RegExp(`(${term})`, 'gi');
            walkTextNodes(content, (node) => {
                const matches = node.textContent.match(regex);
                if (matches) {
                    const span = document.createElement('span');
                    span.innerHTML = node.textContent.replace(regex, '<mark>$1</mark>');
                    node.parentNode.replaceChild(span, node);
                }
            });
        }
    });
}

function walkTextNodes(node, callback) {
    if (node.nodeType === 3) {
        callback(node);
    } else {
        for (let i = 0; i < node.childNodes.length; i++) {
            walkTextNodes(node.childNodes[i], callback);
        }
    }
}

// Add keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('.md-search__input');
        if (searchInput) {
            searchInput.focus();
        }
    }

    // Escape to close search
    if (e.key === 'Escape') {
        const searchInput = document.querySelector('.md-search__input');
        if (searchInput && document.activeElement === searchInput) {
            searchInput.blur();
        }
    }
});
