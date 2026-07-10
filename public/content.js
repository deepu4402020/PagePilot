function getPageContext() {
  const allElements = document.querySelectorAll('input, button, a, textarea, select');
  const elements = [];

  for (const el of allElements) {
    if (elements.length >= 20) break;

    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    if (el.type === 'hidden') continue;

    const label = findLabel(el);
    const selector = buildSelector(el);
    const tagName = el.tagName.toLowerCase();

    const entry = {
      selector,
      tagName,
      type: el.type || null,
      text: (el.textContent || '').trim().slice(0, 100),
      label: label.trim().slice(0, 100),
    };

    if (tagName === 'select') {
      const opts = Array.from(el.options).slice(0, 10);
      entry.options = opts.map(o => ({ value: o.value, text: o.textContent.trim() }));
    }

    elements.push(entry);
  }

  return elements;
}

function findLabel(el) {
  if (el.labels && el.labels[0]?.textContent) {
    return el.labels[0].textContent;
  }
  if (el.getAttribute('aria-label')) {
    return el.getAttribute('aria-label');
  }
  if (el.getAttribute('placeholder')) {
    return el.getAttribute('placeholder');
  }

  const prev = el.previousElementSibling;
  if (prev && prev.tagName.toLowerCase() === 'label') {
    return prev.textContent || '';
  }

  return '';
}

function buildSelector(el) {
  if (el.id) {
    return `#${CSS.escape(el.id)}`;
  }

  const name = el.getAttribute('name');
  if (name) {
    return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
  }

  const testId = el.getAttribute('data-testid');
  if (testId) {
    return `[data-testid="${CSS.escape(testId)}"]`;
  }

  const tag = el.tagName.toLowerCase();
  const parent = el.parentElement;
  if (!parent) return tag;

  const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
  const index = siblings.indexOf(el) + 1;

  let parentScope = parent.tagName.toLowerCase();
  if (parent.classList.length > 0) {
    parentScope += '.' + Array.from(parent.classList).map(c => CSS.escape(c)).join('.');
  }

  return `${parentScope} > ${tag}:nth-of-type(${index})`;
}

function executeAction(action) {
  switch (action.type) {
    case 'click': {
      const el = document.querySelector(action.selector);
      if (el) {
        el.click();
        return { success: true, message: `Clicked ${action.selector}` };
      }
      return { success: false, message: 'Element not found' };
    }

    case 'fill_input': {
      const el = document.querySelector(action.selector);
      if (el) {
        const nativeSetter =
          Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set ||
          Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;

        if (nativeSetter) {
          nativeSetter.call(el, action.value);
        } else {
          el.value = action.value;
        }

        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return { success: true, message: `Filled ${action.selector}` };
      }
      return { success: false, message: 'Element not found' };
    }

    case 'select_option': {
      const el = document.querySelector(action.selector);
      if (el) {
        el.value = action.value;
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return { success: true, message: `Selected ${action.value}` };
      }
      return { success: false, message: 'Element not found' };
    }

    case 'scroll_page': {
      window.scrollBy(0, action.amount || 500);
      return { success: true, message: 'Scrolled page' };
    }

    case 'navigate': {
      window.location.href = action.url;
      return { success: true, message: `Navigating to ${action.url}` };
    }

    default:
      return { success: false, error: `Unknown action type: ${action.type}` };
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract_context') {
    sendResponse({ 
      context: getPageContext(),
      page_text: document.body.innerText.slice(0, 15000) // limit for safety
    });
  }

  if (request.action === 'execute_tool') {
    sendResponse(executeAction(request.tool));
  }

  if (request.action === 'execute_tools') {
    (async () => {
      const results = [];
      for (const tool of request.tools) {
        results.push(executeAction(tool));
        await sleep(300);
      }
      sendResponse(results);
    })();
  }

  return true;
});
