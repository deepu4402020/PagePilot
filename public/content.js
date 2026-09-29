// ============================================================
// PagePilot — DOM Interaction Engine
// Multi-strategy selector generation + runtime fallback chain
// ============================================================

/**
 * Extracts interactive page elements with multiple selector strategies per element.
 * Each element gets a prioritized list of selectors for resilient automation.
 */
function getPageContext() {
  const allElements = document.querySelectorAll('input, button, a, textarea, select, [role="button"], [role="textbox"], [role="combobox"], [contenteditable="true"]');
  const elements = [];

  for (const el of allElements) {
    if (elements.length >= 40) break;
    if (!isVisible(el)) continue;
    if (el.type === 'hidden') continue;

    const label = findLabel(el);
    const selectors = buildSelectorChain(el);
    const tagName = el.tagName.toLowerCase();

    const entry = {
      selector: selectors[0],            // Primary selector (best available)
      fallback_selectors: selectors,      // Full fallback chain for runtime retry
      tagName,
      type: el.type || el.getAttribute('role') || null,
      text: (el.textContent || '').trim().slice(0, 100),
      label: label.trim().slice(0, 100),
    };

    if (tagName === 'select' || el.getAttribute('role') === 'combobox') {
      const opts = Array.from(el.options || []).slice(0, 15);
      entry.options = opts.map(o => ({ value: o.value, text: o.textContent.trim() }));
    }

    elements.push(entry);
  }

  return elements;
}

/**
 * Checks if an element is actually visible and interactable.
 */
function isVisible(el) {
  if (!el.offsetParent && el.tagName !== 'BODY') return false;
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

/**
 * Finds the human-readable label for a form element.
 * Checks: associated <label>, aria-label, aria-labelledby, placeholder, 
 * preceding sibling label, parent label, nearby text.
 */
function findLabel(el) {
  // 1. Associated <label> via 'for' attribute
  if (el.labels && el.labels.length > 0 && el.labels[0].textContent) {
    return el.labels[0].textContent;
  }

  // 2. aria-label
  const ariaLabel = el.getAttribute('aria-label');
  if (ariaLabel) return ariaLabel;

  // 3. aria-labelledby
  const labelledBy = el.getAttribute('aria-labelledby');
  if (labelledBy) {
    const labelEl = document.getElementById(labelledBy);
    if (labelEl?.textContent) return labelEl.textContent;
  }

  // 4. Placeholder
  const placeholder = el.getAttribute('placeholder');
  if (placeholder) return placeholder;

  // 5. Title attribute
  const title = el.getAttribute('title');
  if (title) return title;

  // 6. Preceding sibling label
  const prev = el.previousElementSibling;
  if (prev && prev.tagName.toLowerCase() === 'label') {
    return prev.textContent || '';
  }

  // 7. Parent label element
  const parentLabel = el.closest('label');
  if (parentLabel) {
    return parentLabel.textContent || '';
  }

  // 8. Button/link text content
  if (['button', 'a'].includes(el.tagName.toLowerCase())) {
    return el.textContent || '';
  }

  return '';
}

/**
 * Builds a prioritized chain of CSS selectors for an element.
 * Returns multiple strategies ordered from most stable to least stable.
 * At execution time, the engine tries each until one matches.
 * 
 * Priority: id > name > data-testid > aria-label > role+type > structural
 */
function buildSelectorChain(el) {
  const selectors = [];

  // Strategy 1: ID selector (most stable)
  if (el.id) {
    selectors.push(`#${CSS.escape(el.id)}`);
  }

  // Strategy 2: name attribute
  const name = el.getAttribute('name');
  if (name) {
    selectors.push(`${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`);
  }

  // Strategy 3: data-testid (test-friendly)
  const testId = el.getAttribute('data-testid');
  if (testId) {
    selectors.push(`[data-testid="${CSS.escape(testId)}"]`);
  }

  // Strategy 4: data-qa or data-cy (common in CI/CD)
  for (const attr of ['data-qa', 'data-cy', 'data-automation-id']) {
    const val = el.getAttribute(attr);
    if (val) {
      selectors.push(`[${attr}="${CSS.escape(val)}"]`);
    }
  }

  // Strategy 5: aria-label (semantic)
  const ariaLabel = el.getAttribute('aria-label');
  if (ariaLabel) {
    selectors.push(`${el.tagName.toLowerCase()}[aria-label="${CSS.escape(ariaLabel)}"]`);
  }

  // Strategy 6: type + placeholder combo (form inputs)
  const type = el.getAttribute('type');
  const placeholder = el.getAttribute('placeholder');
  if (type && placeholder) {
    selectors.push(`${el.tagName.toLowerCase()}[type="${CSS.escape(type)}"][placeholder="${CSS.escape(placeholder)}"]`);
  }

  // Strategy 7: Structural selector (least stable, always available as fallback)
  const structuralSelector = buildStructuralSelector(el);
  if (structuralSelector) {
    selectors.push(structuralSelector);
  }

  // Deduplicate while preserving order
  return [...new Set(selectors)];
}

/**
 * Builds a structural CSS selector as the last-resort fallback.
 * Uses nth-of-type with parent context for uniqueness.
 */
function buildStructuralSelector(el) {
  const tag = el.tagName.toLowerCase();
  const parent = el.parentElement;
  if (!parent) return tag;

  const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
  const index = siblings.indexOf(el) + 1;

  let parentScope = parent.tagName.toLowerCase();
  if (parent.id) {
    parentScope = `#${CSS.escape(parent.id)}`;
  } else if (parent.classList.length > 0) {
    // Use only stable-looking classes (skip hashed/dynamic ones)
    const stableClasses = Array.from(parent.classList)
      .filter(c => !c.match(/^[a-z]{1,3}-[a-zA-Z0-9]{5,}$/)) // Filter hashed classes like 'css-1a2b3c'
      .filter(c => !c.match(/^_/))                              // Filter module-scoped classes
      .slice(0, 2);
    if (stableClasses.length > 0) {
      parentScope += '.' + stableClasses.map(c => CSS.escape(c)).join('.');
    }
  }

  return `${parentScope} > ${tag}:nth-of-type(${index})`;
}

// ============================================================
// Action Execution Engine with Fallback & Wait-for-Element
// ============================================================

/**
 * Resolves an element using the fallback selector chain.
 * Tries each selector in order until one matches.
 * Optionally waits for dynamic content (SPAs with lazy loading).
 */
async function resolveElement(action, waitMs = 2000) {
  // Build the selector chain: primary selector + any fallbacks
  const selectors = action.fallback_selectors || [action.selector];

  // First pass: try all selectors immediately
  for (const sel of selectors) {
    try {
      const el = document.querySelector(sel);
      if (el && isVisible(el)) return { el, usedSelector: sel };
    } catch (e) {
      // Invalid selector syntax, skip
      continue;
    }
  }

  // Second pass: wait and retry (handles SPAs with lazy-loaded content)
  if (waitMs > 0) {
    const startTime = Date.now();
    while (Date.now() - startTime < waitMs) {
      await sleep(200);
      for (const sel of selectors) {
        try {
          const el = document.querySelector(sel);
          if (el && isVisible(el)) return { el, usedSelector: sel };
        } catch (e) {
          continue;
        }
      }
    }
  }

  return null;
}

/**
 * Executes a browser action with the fallback selector chain.
 * Uses resolveElement to find the target, then performs the action.
 */
async function executeAction(action) {
  switch (action.type) {
    case 'click': {
      const result = await resolveElement(action);
      if (result) {
        result.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        await sleep(100);
        result.el.click();
        return { success: true, message: `Clicked ${result.usedSelector}` };
      }
      return { success: false, message: `Element not found. Tried ${(action.fallback_selectors || [action.selector]).length} selector(s).` };
    }

    case 'fill_input': {
      const result = await resolveElement(action);
      if (result) {
        const el = result.el;
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.focus();
        await sleep(50);

        // React/SPA-compatible value setting via native setter
        const nativeSetter =
          Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set ||
          Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;

        if (nativeSetter) {
          nativeSetter.call(el, action.value);
        } else {
          el.value = action.value;
        }

        // Dispatch events that React and other frameworks listen for
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
        return { success: true, message: `Filled ${result.usedSelector} with "${action.value.substring(0, 30)}..."` };
      }
      return { success: false, message: `Element not found. Tried ${(action.fallback_selectors || [action.selector]).length} selector(s).` };
    }

    case 'select_option': {
      const result = await resolveElement(action);
      if (result) {
        const el = result.el;
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Try exact value match first, then text-based match
        let matched = false;
        for (const opt of el.options || []) {
          if (opt.value === action.value || opt.textContent.trim().toLowerCase() === action.value.toLowerCase()) {
            el.value = opt.value;
            matched = true;
            break;
          }
        }

        if (!matched) {
          // Fuzzy match: find closest option
          const target = action.value.toLowerCase();
          let bestMatch = null;
          let bestScore = 0;
          for (const opt of el.options || []) {
            const text = opt.textContent.trim().toLowerCase();
            if (text.includes(target) || target.includes(text)) {
              const score = Math.min(text.length, target.length) / Math.max(text.length, target.length);
              if (score > bestScore) {
                bestScore = score;
                bestMatch = opt;
              }
            }
          }
          if (bestMatch) {
            el.value = bestMatch.value;
            matched = true;
          }
        }

        el.dispatchEvent(new Event('change', { bubbles: true }));
        return { 
          success: matched, 
          message: matched ? `Selected "${action.value}" in ${result.usedSelector}` : `No matching option for "${action.value}"` 
        };
      }
      return { success: false, message: `Element not found. Tried ${(action.fallback_selectors || [action.selector]).length} selector(s).` };
    }

    case 'scroll_page': {
      window.scrollBy({ top: action.amount || 500, behavior: 'smooth' });
      return { success: true, message: `Scrolled ${action.amount || 500}px` };
    }

    case 'navigate': {
      window.location.href = action.url;
      return { success: true, message: `Navigating to ${action.url}` };
    }

    default:
      return { success: false, message: `Unknown action type: ${action.type}` };
  }
}

// ============================================================
// Utilities
// ============================================================

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================
// Chrome Extension Message Handler
// ============================================================

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract_context') {
    sendResponse({
      context: getPageContext(),
      page_text: document.body.innerText.slice(0, 15000)
    });
    return true;
  }

  if (request.action === 'execute_tool') {
    // Use async execution with fallback chain
    executeAction(request.tool).then(result => {
      sendResponse(result);
    }).catch(err => {
      sendResponse({ success: false, message: `Error: ${err.message}` });
    });
    return true; // Keep message channel open for async response
  }

  if (request.action === 'execute_tools') {
    (async () => {
      const results = [];
      for (const tool of request.tools) {
        const result = await executeAction(tool);
        results.push(result);
        await sleep(300);
      }
      sendResponse(results);
    })();
    return true;
  }

  return true;
});
