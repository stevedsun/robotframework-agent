() => {
  // NOTE: nothing may precede the arrow function in this file — the Browser
  // library wraps the script as `new Function("return " + script)()`, and a
  // leading comment line breaks that through ASI.
  //
  // Observation collector, executed inside the page via Browser's
  // `Evaluate JavaScript`. Walks the DOM in document order, tags every
  // interactive element with a stable id (data-rfa-id, kept across calls via
  // a WeakMap on window.__rfa) and returns structured JSON that
  // observation.py formats as model input. Ids stay valid as long as their
  // element lives; after a navigation every id is re-assigned from scratch,
  // which the agent rules tell the model to expect.
  const state = (window.__rfa = window.__rfa || { next: 1, ids: new WeakMap() });
  const ATTR = 'data-rfa-id';
  const MAX_ITEMS = 300;

  const INTERACTIVE = [
    'a[href]', 'button', 'input', 'select', 'textarea', 'summary',
    '[role="button"]', '[role="link"]', '[role="checkbox"]', '[role="radio"]',
    '[role="tab"]', '[role="menuitem"]', '[role="option"]', '[role="switch"]',
    '[role="textbox"]', '[role="combobox"]', '[role="searchbox"]',
    '[role="slider"]', '[role="spinbutton"]',
    '[contenteditable=""]', '[contenteditable="true"]', '[onclick]', '[tabindex]'
  ].join(',');
  const HEADINGS = 'h1,h2,h3,h4,h5,h6,[role="heading"],[role="alert"],[role="status"]';
  const TEXTY = 'p,li,td,th,label,legend,caption,figcaption,output,dd,dt';
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'META', 'LINK']);

  function idFor(el) {
    let id = state.ids.get(el);
    if (!id) {
      id = 'n' + state.next++;
      state.ids.set(el, id);
    }
    el.setAttribute(ATTR, id);
    return id;
  }

  function clean(s, limit) {
    const t = String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
    return t.length > limit ? t.slice(0, limit - 1) + '…' : t;
  }

  function isShown(el) {
    const cs = window.getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse') return false;
    const r = el.getBoundingClientRect();
    return r.width >= 2 && r.height >= 2;
  }

  function roleOf(el) {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit;
    switch (el.tagName.toLowerCase()) {
      case 'a': return 'link';
      case 'button': return 'button';
      case 'select': return 'combobox';
      case 'textarea': return 'textbox';
      case 'summary': return 'button';
      case 'input': {
        const type = (el.getAttribute('type') || 'text').toLowerCase();
        if (['button', 'submit', 'reset'].includes(type)) return 'button';
        if (type === 'checkbox') return 'checkbox';
        if (type === 'radio') return 'radio';
        if (type === 'range') return 'slider';
        if (['hidden', 'file', 'image'].includes(type)) return null;
        return 'textbox';
      }
      default: return 'generic';
    }
  }

  function labelFor(el) {
    if (el.id) {
      const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (lab) return clean(lab.innerText, 80);
    }
    const wrapping = el.closest('label');
    if (wrapping) return clean(wrapping.innerText, 80);
    const by = el.getAttribute('aria-labelledby');
    if (by) {
      const t = by.split(/\s+/).map((x) => {
        const n = document.getElementById(x);
        return n ? n.innerText : '';
      }).join(' ');
      if (t.trim()) return clean(t, 80);
    }
    return '';
  }

  function nameOf(el) {
    const aria = el.getAttribute('aria-label');
    if (aria) return clean(aria, 80);
    const lab = labelFor(el);
    if (lab) return lab;
    const ph = el.getAttribute('placeholder');
    if (ph) return clean(ph, 80);
    const alt = el.getAttribute('alt');
    if (alt) return clean(alt, 80);
    const title = el.getAttribute('title');
    if (title) return clean(title, 80);
    const tag = el.tagName.toLowerCase();
    if (tag === 'input') {
      const type = (el.getAttribute('type') || 'text').toLowerCase();
      if (['button', 'submit', 'reset'].includes(type)) return clean(el.value, 80);
    }
    return clean(el.innerText, 80);
  }

  function valueOf(el, node) {
    const tag = el.tagName.toLowerCase();
    if (tag === 'input') {
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (type === 'password') { node.value = '<hidden>'; return; }
      if (type === 'checkbox' || type === 'radio') { node.checked = !!el.checked; return; }
      if (!['button', 'submit', 'reset', 'hidden', 'file', 'image'].includes(type)) {
        node.value = clean(el.value, 80);
      }
      return;
    }
    if (tag === 'textarea') { node.value = clean(el.value, 80); return; }
    if (tag === 'select') {
      const opt = el.options[el.selectedIndex];
      node.value = opt ? clean(opt.text, 80) : '';
    }
  }

  const items = [];
  let truncated = false;

  function walk(el, depth) {
    if (items.length >= MAX_ITEMS) { truncated = true; return; }
    if (SKIP.has(el.tagName)) return;
    const cs = window.getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return; // whole subtree invisible

    if (el.matches(INTERACTIVE)) {
      const role = roleOf(el);
      if (role && isShown(el)) {
        const node = { kind: 'node', id: idFor(el), role, depth, name: nameOf(el) };
        valueOf(el, node);
        items.push(node);
        return; // an interactive element's inner text is its name; don't descend
      }
    }
    if (el.matches(HEADINGS + ',' + TEXTY)) {
      // Report only leaf-ish text blocks: anything with a reportable descendant
      // is reported through that descendant instead.
      if (!el.querySelector(INTERACTIVE + ',' + HEADINGS + ',' + TEXTY)) {
        const t = clean(el.innerText, 120);
        if (t && isShown(el)) items.push({ kind: 'text', depth, text: t });
        return;
      }
    }
    for (const child of el.children) walk(child, depth + 1);
  }

  if (document.body) walk(document.body, 0);

  return {
    url: location.href,
    title: document.title,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    items,
    truncated
  };
}
