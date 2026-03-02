# View Mode Toggle (Infinite Scroll / Pagination) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a toggle on the Saved Tweets page letting the user switch between infinite scroll and paginated browsing, with preference saved to localStorage.

**Architecture:** Pure frontend change to `templates/saved.html`. The `/api/saved` endpoint already returns `total` and supports `page`/`per_page` params, so no backend changes are needed. A `viewMode` variable drives which UI elements are visible and whether the scroll listener is active.

**Tech Stack:** Vanilla JS, Bootstrap 5 button-group, localStorage

---

### Task 1: Add toggle button group and pagination controls HTML

**Files:**
- Modify: `templates/saved.html`

**Context:** The page header is a flex row with `<h2>` on the left and a Refresh button on the right (lines 6–11). The saved-container div (line 40) holds the grid, lazy-loading indicator, and no-more-data indicator.

**Step 1: Replace the page header**

Find (lines 6–11):
```html
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2><i class="bi bi-archive"></i> Saved Tweets</h2>
    <button class="btn btn-outline-primary" onclick="loadSaved()">
        <i class="bi bi-arrow-clockwise"></i> Refresh
    </button>
</div>
```

Replace with:
```html
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2><i class="bi bi-archive"></i> Saved Tweets</h2>
    <div class="d-flex align-items-center gap-2">
        <div class="btn-group btn-group-sm" role="group" aria-label="View mode">
            <button type="button" class="btn btn-outline-secondary" id="btn-infinite"
                    onclick="setViewMode('infinite')" title="Infinite Scroll">
                <i class="bi bi-arrow-down-circle"></i>
            </button>
            <button type="button" class="btn btn-outline-secondary" id="btn-paginated"
                    onclick="setViewMode('paginated')" title="Pagination">
                <i class="bi bi-file-earmark-text"></i>
            </button>
        </div>
        <button class="btn btn-outline-primary btn-sm" onclick="reloadSaved()">
            <i class="bi bi-arrow-clockwise"></i> Refresh
        </button>
    </div>
</div>
```

**Step 2: Add pagination controls inside `saved-container`**

Find (lines 53–58):
```html
            <!-- All loaded indicator -->
            <div id="no-more-data" class="text-center py-4 hidden">
                <i class="bi bi-check-circle text-success"></i>
                <p class="text-muted mt-2 mb-0">All tweets loaded</p>
            </div>
        </div>
```

Replace with:
```html
            <!-- All loaded indicator -->
            <div id="no-more-data" class="text-center py-4 hidden">
                <i class="bi bi-check-circle text-success"></i>
                <p class="text-muted mt-2 mb-0">All tweets loaded</p>
            </div>

            <!-- Pagination controls -->
            <div id="pagination-controls" class="d-flex justify-content-between align-items-center mt-3 hidden">
                <button class="btn btn-outline-secondary btn-sm" id="btn-prev" onclick="goToPrevPage()">
                    <i class="bi bi-chevron-left"></i> Prev
                </button>
                <span id="page-info" class="text-muted small">Page 1</span>
                <button class="btn btn-outline-secondary btn-sm" id="btn-next" onclick="goToNextPage()">
                    Next <i class="bi bi-chevron-right"></i>
                </button>
            </div>
        </div>
```

**Step 3: Commit**
```bash
cd /home/huang/twitter_collector
git add templates/saved.html
git commit -m "feat: add view mode toggle button and pagination controls HTML"
```

---

### Task 2: Update JavaScript to support both modes

**Files:**
- Modify: `templates/saved.html` (the `{% block scripts %}` section)

**Context:** The current JS lives in `{% block scripts %}` starting at line 284. Key state variables: `currentPage`, `perPage = 12`, `currentSearchQuery`, `isLoading`, `hasMoreData`, `isInitialLoad`. The scroll listener is attached at the bottom (line 671).

**Step 1: Replace the state variable declarations**

Find (lines 286–291):
```javascript
    let currentPage = 1;
    const perPage = 12;
    let currentSearchQuery = '';
    let isLoading = false;
    let hasMoreData = true;
    let isInitialLoad = true;
```

Replace with:
```javascript
    let currentPage = 1;
    const perPage = 12;
    let currentSearchQuery = '';
    let isLoading = false;
    let hasMoreData = true;
    let isInitialLoad = true;
    let totalPages = 1;
    let viewMode = localStorage.getItem('savedViewMode') || 'infinite';
```

**Step 2: Add `setViewMode`, `applyViewMode`, `updatePaginationControls`, `goToPrevPage`, `goToNextPage`, `reloadSaved` functions**

Find the line:
```javascript
    // Load saved tweets list
    function loadSaved(page = 1, searchQuery = '', append = false) {
```

Insert these functions immediately before it:
```javascript
    // --- View mode ---

    function setViewMode(mode) {
        viewMode = mode;
        localStorage.setItem('savedViewMode', mode);
        applyViewMode();
        currentPage = 1;
        hasMoreData = true;
        loadSaved(1, currentSearchQuery, false);
    }

    function applyViewMode() {
        const btnInfinite = document.getElementById('btn-infinite');
        const btnPaginated = document.getElementById('btn-paginated');
        const paginationControls = document.getElementById('pagination-controls');
        const noMoreData = document.getElementById('no-more-data');

        if (viewMode === 'infinite') {
            btnInfinite.classList.add('active');
            btnPaginated.classList.remove('active');
            hideElement(paginationControls);
            window.addEventListener('scroll', throttledScrollCheck);
        } else {
            btnPaginated.classList.add('active');
            btnInfinite.classList.remove('active');
            showElement(paginationControls);
            hideElement(noMoreData);
            window.removeEventListener('scroll', throttledScrollCheck);
        }
    }

    function updatePaginationControls() {
        if (viewMode !== 'paginated') return;
        document.getElementById('btn-prev').disabled = currentPage <= 1;
        document.getElementById('btn-next').disabled = currentPage >= totalPages;
        document.getElementById('page-info').textContent = totalPages > 0
            ? `Page ${currentPage} / ${totalPages}`
            : 'No results';
    }

    function goToPrevPage() {
        if (currentPage > 1) {
            loadSaved(currentPage - 1, currentSearchQuery, false);
            window.scrollTo(0, 0);
        }
    }

    function goToNextPage() {
        if (currentPage < totalPages) {
            loadSaved(currentPage + 1, currentSearchQuery, false);
            window.scrollTo(0, 0);
        }
    }

    function reloadSaved() {
        currentPage = 1;
        hasMoreData = true;
        loadSaved(1, currentSearchQuery, false);
    }

    // --- End view mode ---

```

**Step 3: Update `loadSaved` to handle paginated mode and set `totalPages`**

Inside `loadSaved`, find the block that processes a successful response with data (find this section):
```javascript
                showElement(container);

                if (append) {
                    // Lazy load: append to existing content
                    appendSaved(data.saved);
                } else {
                    // First load or search: replace content
                    renderSaved(data.saved);
                }

                currentPage = page;

                // Check if there is more data
                if (data.saved.length < perPage) {
                    hasMoreData = false;
                    if (!isInitialLoad) {
                        showElement(noMoreData);
                    }
                } else {
                    hasMoreData = true;
                }

                isInitialLoad = false;
```

Replace with:
```javascript
                showElement(container);

                if (append) {
                    // Lazy load: append to existing content
                    appendSaved(data.saved);
                } else {
                    // First load or search: replace content
                    renderSaved(data.saved);
                }

                currentPage = page;
                totalPages = Math.ceil((data.total || 0) / perPage) || 1;

                if (viewMode === 'paginated') {
                    updatePaginationControls();
                } else {
                    // Infinite scroll: check if there is more data
                    if (data.saved.length < perPage) {
                        hasMoreData = false;
                        if (!isInitialLoad) {
                            showElement(noMoreData);
                        }
                    } else {
                        hasMoreData = true;
                    }
                }

                isInitialLoad = false;
```

**Step 4: Update the scroll listener initialization at the bottom**

Find (lines 669–677):
```javascript
    // Initialize scroll event listener
    const throttledScrollCheck = throttle(checkScrollPosition, 200);
    window.addEventListener('scroll', throttledScrollCheck);

    // Also check scroll position when window is resized
    window.addEventListener('resize', throttledScrollCheck);

    // Initial load
    loadSaved();
```

Replace with:
```javascript
    // Initialize scroll event listener
    const throttledScrollCheck = throttle(checkScrollPosition, 200);

    // Also check scroll position when window is resized
    window.addEventListener('resize', throttledScrollCheck);

    // Apply saved view mode preference and initial load
    applyViewMode();
    loadSaved();
```

**Step 5: Commit**
```bash
cd /home/huang/twitter_collector
git add templates/saved.html
git commit -m "feat: implement infinite scroll / pagination toggle with localStorage persistence"
```

---

### Task 3: Push

```bash
cd /home/huang/twitter_collector
git push
```

---

## Manual Verification Checklist

1. Start server: `python run_web.py`
2. Visit `/saved` — page loads in default mode (infinite scroll)
3. Two small icons visible in the header next to Refresh — scroll icon active/highlighted
4. Scroll to bottom — more tweets auto-load (infinite scroll works)
5. Click the pagination icon — mode switches, pagination controls appear at bottom
6. "Page 1 / N" shown correctly, Prev disabled, Next enabled if multiple pages
7. Click Next — page 2 loads, Prev enabled
8. Click Prev — back to page 1
9. Search for something — results update, page resets to 1
10. Refresh the page — pagination mode is remembered from localStorage
11. Switch back to infinite scroll — scroll listener reactivated, pagination controls hidden
