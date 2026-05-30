(function () {
  const streamNode = document.getElementById("chat-stream");
  const formNode = document.getElementById("chat-form");
  const inputNode = document.getElementById("chat-input");
  const voiceToggleButton = document.getElementById("voice-toggle-button");
  const voiceInputButton = document.getElementById("voice-input-button");
  const statusNode = document.getElementById("chat-status-pill");
  const voiceVisualNode = document.getElementById("voice-visual");
  const voiceCopyNode = document.getElementById("voice-copy");
  const promptButtons = document.querySelectorAll("[data-prompt]");
  const state = {
    voiceEnabled: false,
    listening: false,
    recognition: null,
    preferredLang: "auto", // 'auto' | 'en' | 'ne'
    lastAccount: null,
    // Load persisted session phone from localStorage so verification survives reloads
    sessionPhone: window.localStorage.getItem('awaj_session_phone') || null,
  };

  const formatMoney = (value) => {
    const amount = Number(value);
    if (Number.isNaN(amount)) {
      return String(value);
    }
    return `Rs. ${amount.toFixed(2)}`;
  };

  const formatDate = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const appendBubble = (role, title, text) => {
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble chat-bubble-${role}`;

    const heading = document.createElement("strong");
    heading.textContent = title;

    const body = document.createElement("p");
    body.textContent = text;

    bubble.append(heading, body);
    streamNode.appendChild(bubble);
    streamNode.scrollTop = streamNode.scrollHeight;
    return bubble;
  };

  const setStatus = (text) => {
    statusNode.textContent = text;
  };

  const setListeningState = (isListening) => {
    state.listening = isListening;
    voiceInputButton.classList.toggle("is-listening", isListening);
    voiceVisualNode.classList.toggle("is-listening", isListening);
    statusNode.classList.toggle("is-listening", isListening);
    voiceCopyNode.textContent = isListening
      ? "Awaj AI is listening to your microphone right now."
      : "Press Use mic to start speech recognition in browsers that support it.";
    voiceInputButton.textContent = isListening ? "Listening..." : "Use mic";
    voiceInputButton.setAttribute("aria-pressed", String(isListening));
  };

  const speak = (text) => {
    if (!state.voiceEnabled || !window.speechSynthesis) {
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    // Choose TTS language: user preference overrides auto-detection.
    const chooseLang = () => {
      if (state.preferredLang === "en") return "en-US";
      if (state.preferredLang === "ne") return "ne-NP";
      // auto: detect simple indicators (Devanagari chars or Nepali keywords)
      const devMatch = /[\u0900-\u097F]/.test(text);
      const nepaliWords = /\b(हाम्रो|मलाई|तपाईं|कसरी|धन्यवाद|नमस्ते|छ)\b/i;
      if (devMatch || nepaliWords.test(text)) return "ne-NP";
      return "en-US";
    };

    utterance.lang = chooseLang();
    window.speechSynthesis.speak(utterance);
  };

  const cycleLang = () => {
    if (state.preferredLang === "auto") state.preferredLang = "en";
    else if (state.preferredLang === "en") state.preferredLang = "ne";
    else state.preferredLang = "auto";
    const btn = document.getElementById("lang-toggle-button");
    btn.textContent = state.preferredLang === "auto" ? "Lang: Auto" : state.preferredLang === "en" ? "Lang: English" : "Lang: Nepali";
    btn.setAttribute("aria-pressed", String(state.preferredLang !== "auto"));
  };

  const detectLangFromInput = (input) => {
    if (state.preferredLang === "en") return "en";
    if (state.preferredLang === "ne") return "ne";
    // auto: detect Devanagari or Nepali words in the input
    if (!input) return "en";
    const devMatch = /[\u0900-\u097F]/.test(input);
    const nepaliWords = /\b(मेरो|नमस्ते|धन्यवाद|कसरी|मलाई|तपाईं)\b/i;
    if (devMatch || nepaliWords.test(input)) return "ne";
    return "en";
  };

  // PROMPTS loader: fetch assistprompt.json via the API endpoint we expose
  let PROMPTS = null;
  const loadPrompts = async () => {
    try {
      const resp = await fetch('/api/prompts', { cache: 'no-store' });
      if (resp.ok) {
        const json = await resp.json();
        PROMPTS = json.data || null;
        return;
      }
    } catch (e) {
      // ignore and fall back
    }
    PROMPTS = null; // keep null to trigger fallback
  };
  // Kick off loading but don't await blocking startup
  loadPrompts();

  // Helper to read CSRF cookie for safe POST requests
  const getCookie = (name) => {
    if (!document.cookie) return null;
    const cookies = document.cookie.split(';').map(c => c.trim());
    for (const c of cookies) {
      if (c.startsWith(name + '=')) return decodeURIComponent(c.split('=')[1]);
    }
    return null;
  };

  // Sync with server-side session on startup. If server has a saved phone,
  // prefer that and write it to localStorage so client and server stay in sync.
  const loadServerSessionPhone = async () => {
    try {
      const resp = await fetch('/api/session-phone', { headers: { Accept: 'application/json' } });
      if (!resp.ok) return;
      const payload = await resp.json();
      const phone = payload && payload.data && payload.data.phone;
      if (phone) {
        state.sessionPhone = phone;
        try { window.localStorage.setItem('awaj_session_phone', String(phone)); } catch (e) {}
        try { console.log('[AwajAI] loaded session phone from server:', phone); } catch (e) {}
      }
    } catch (e) {
      // ignore failures — client-side localStorage will still work
    }
  };

  // Set session phone on the server (POST). Includes CSRF token when available.
  const setSessionPhoneOnServer = async (phone) => {
    try {
      const csrf = getCookie('csrftoken');
      await fetch('/api/session-phone', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrf ? { 'X-CSRFToken': csrf } : {}),
          Accept: 'application/json',
        },
        body: JSON.stringify({ phone }),
        credentials: 'same-origin',
      });
      try { console.log('[AwajAI] session phone set on server:', phone); } catch (e) {}
    } catch (e) {
      try { console.log('[AwajAI] failed to set session phone on server', e); } catch (e) {}
    }
  };

  // Load server session phone once at startup
  loadServerSessionPhone();

  // Quick Questions: fetch configuration and render clickable chips above composer
  const renderQuickQuestions = (groups) => {
    const container = document.getElementById('quick-questions-container');
    if (!container || !Array.isArray(groups)) return;
    container.innerHTML = '';
    groups.forEach((g) => {
      const group = document.createElement('div');
      group.className = 'quick-group';
      // hide the Account header for a cleaner UI while keeping its chips
      const showTitle = (g.category || '').toLowerCase() !== 'account';
      if (showTitle) {
        const title = document.createElement('h3');
        title.className = 'quick-group-title';
        title.textContent = g.category || '';
        group.appendChild(title);
      }

      const list = document.createElement('div');
      list.className = 'quick-chip-list';
      (g.questions || []).forEach((q) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'prompt-chip quick-chip';
        btn.setAttribute('aria-label', `${g.category}: ${q}`);
        btn.textContent = q;
        btn.dataset.question = q;
        // click sends message immediately
        btn.addEventListener('click', (ev) => {
          ev.preventDefault();
          handleAssistantResponse(q);
        });
        // keyboard accessibility
        btn.addEventListener('keydown', (ev) => {
          if (ev.key === 'Enter' || ev.key === ' ') {
            ev.preventDefault();
            handleAssistantResponse(q);
          }
        });
        list.appendChild(btn);
      });
      group.appendChild(list);
      container.appendChild(group);
    });
  };

  const loadQuickQuestions = async () => {
    try {
      const resp = await fetch('/api/quick-questions', { headers: { Accept: 'application/json' } });
      if (!resp.ok) return;
      const payload = await resp.json();
      const data = payload && payload.data;
      if (data) renderQuickQuestions(data);
    } catch (e) {
      // ignore failures
    }
  };

  loadQuickQuestions();

  const substituteParams = (template, params) => {
    if (!template) return '';
    let out = String(template);
    Object.keys(params || {}).forEach((k) => {
      const v = params[k] === undefined || params[k] === null ? '' : String(params[k]);
      out = out.split(`{${k}}`).join(v);
    });
    return out;
  };

  const isLikelyFaqQuestion = (text) => {
    if (!text) return false;
    const t = text.trim().toLowerCase();
    // question mark or common FAQ triggers
    if (t.endsWith('?')) return true;
    const triggers = ['roll over', 'rollover', 'unused', 'how do i', 'how to', 'how', 'can i', 'change my plan', 'check my', 'balance'];
    for (const tr of triggers) {
      if (t.includes(tr)) return true;
    }
    // Nepali triggers
    const nep = /(कसरी|किन|मेरो|के|कुन|कति|रोल|रोलओभर|प्लान|प्याकेज)/;
    if (nep.test(t)) return true;
    return false;
  };

  // Minimal fallback messages in case assistprompt.json cannot be fetched.
  const FALLBACK = {
    en: {
      ask_what_to_know: 'What would you like to know: balance, expiry date, or your packages?',
      ask_for_phone: 'Please provide your phone number so I can look up your balance.',
      account_summary: '{name} is on {plan}. Balance is {balance}, due {due}, with {data} GB, {minutes} minutes, and {sms} SMS left.',
      due_date: 'Your due date is {due} for {plan}.',
      package_details: '{name} is on {plan}. {package_name} includes {data_gb} GB, {voice_minutes} minutes, and {sms_count} SMS.',
      high_data_explain: 'Common reasons your data may be used quickly: background apps, video streaming, automatic updates, or hotspot usage.',
      data_fast_tips: 'To reduce usage: disable background data, lower video quality, do large updates on Wi‑Fi, and check data-usage in your provider app.',
      faq_result_prefix: '{question} {answer}',
    },
    ne: {
      ask_what_to_know: 'के जान्न चाहनुहुन्छ: ब्यालेन्स, अवधि (due date), वा तपाईंको प्याकेजहरू?',
      ask_for_phone: 'कृपया तपाईंको फोन नम्बर दिनुहोस् ताकि म तपाईंको ब्यालेन्स हेर्न सकूँ।',
      account_summary: '{name} {plan} मा छन्। ब्यालेन्स {balance} छ, देय {due} मा छ, {data} जीबी, {minutes} मिनेट, र {sms} एसएमएस बाँकी छ।',
      due_date: '{plan} को देय मिति {due} हो।',
      package_details: '{name} {plan} मा छन्। {package_name} मा {data_gb} जीबी, {voice_minutes} मिनेट, र {sms_count} एसएमएस समावेश छन्।',
      high_data_explain: 'तपाईंको डाटा छिटो सकिनुका सामान्य कारणहरू: पृष्ठभूमि एपहरू, भिडियो स्ट्रिमिङ, स्वत: अपडेटहरू, वा हॉटस्पट प्रयोग।',
      data_fast_tips: 'खुट्टामा: पृष्ठभूमि डेटा बन्द गर्नुहोस्, भिडियो क्वालिटी घटाउनुहोस्, ठूला अपडेटहरू Wi‑Fi मा गर्नुहोस्, र डेटा प्रयोग जाँच गर्नुहोस्।',
      faq_result_prefix: '{question} {answer}',
    },
  };

  const localize = (key, params = {}, lang = 'en') => {
    const chosenLang = (lang || 'en');
    // prepare formatted params
    const safeParams = Object.assign({}, params);
    if (safeParams.balance !== undefined) safeParams.balance = formatMoney(safeParams.balance);
    if (safeParams.due !== undefined) safeParams.due = formatDate(safeParams.due);
    if (safeParams.data !== undefined) safeParams.data = String(safeParams.data);
    if (safeParams.data_gb !== undefined) safeParams.data_gb = String(safeParams.data_gb);
    // use PROMPTS if available
    let template = null;
    if (PROMPTS && PROMPTS[chosenLang] && PROMPTS[chosenLang][key]) {
      template = PROMPTS[chosenLang][key];
    } else if (FALLBACK[chosenLang] && FALLBACK[chosenLang][key]) {
      template = FALLBACK[chosenLang][key];
    } else {
      // last resort: empty string
      template = '';
    }

    return substituteParams(template, safeParams);
  };

  const parsePhoneNumber = (text) => {
    // Normalize by removing non-digit characters and validate length.
    if (!text) return null;
    const digits = (text || "").replace(/\D/g, "");
    if (digits.length >= 7 && digits.length <= 15) {
      return digits;
    }
    return null;
  };

  const parsePackageQuery = (text) => {
    const lower = text.toLowerCase();
    const packageMatch = lower.match(/(?:package|plan)\s*(?:id|number)?\s*([a-z0-9_-]+)/i);
    if (packageMatch) {
      return packageMatch[1];
    }

    if (lower.includes("starter")) {
      return "TelConnect Starter";
    }
    if (lower.includes("smart")) {
      return "TelConnect Smart";
    }
    if (lower.includes("plus")) {
      return "TelConnect Plus";
    }

    return null;
  };

  const parseFaqQuery = (text) => {
    const cleaned = text.replace(/^.*?(faq|help|about)\s*/i, "").trim();
    return cleaned || text.trim();
  };

  // Intent normalization and fuzzy matching helpers
  const _levenshtein = (a, b) => {
    // simple Levenshtein distance
    const al = a.length, bl = b.length;
    if (al === 0) return bl;
    if (bl === 0) return al;
    const v0 = new Array(bl + 1);
    const v1 = new Array(bl + 1);
    for (let i = 0; i <= bl; i++) v0[i] = i;
    for (let i = 0; i < al; i++) {
      v1[0] = i + 1;
      for (let j = 0; j < bl; j++) {
        const cost = a[i] === b[j] ? 0 : 1;
        v1[j + 1] = Math.min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost);
      }
      for (let j = 0; j <= bl; j++) v0[j] = v1[j];
    }
    return v1[bl];
  };

  const similarityRatio = (a, b) => {
    if (!a || !b) return 0;
    a = a.toLowerCase().trim();
    b = b.toLowerCase().trim();
    const dist = _levenshtein(a, b);
    const maxLen = Math.max(a.length, b.length);
    if (maxLen === 0) return 1;
    return 1 - dist / maxLen;
  };

  const EXPIRY_TERMS = [
    // English
    'expiry','expire','expiration','expiry date','exp date','valid until','due date','xperidate','expirated','ex','exp',
    // Nepali
    'म्याद','म्याद कहिले सकिन्छ','कहिलेसम्म चल्छ','सकिने मिति','एक्सपायर','अवधि'
  ];

  const BALANCE_TERMS = [
    'balance','remaining balance','account balance','current balance','balence','ब्यालेन्स','ब्यालेन्स कति छ','पैसा कति बाँकी छ'
  ];

  const PACKAGE_TERMS = [
    'package','pack','plan','my plan','current plan','package details','pakage','प्याकेज','प्लान','मेरो प्लान','मेरो प्याकेज','प्याकेज'
  ];

  const SUPPORT_TERMS = [
    'internet','slow','network','signal','not working','speed','connection','network issue','internet not working',
    // Nepali
    'इन्टरनेट','इन्टरनेट चल्दैन','नेटवर्क','सिग्नल','छिटो छैन','जडान','सर्भर'
  ];

  const normalizeIntent = (text) => {
    // Returns { intent: 'balance'|'expiry'|'package'|'support'|'faq'|'unknown', confidence: 0.0-1.0 }
    const out = { intent: 'unknown', confidence: 0.0 };
    if (!text) return out;
    const t = text.toLowerCase().trim();

    // direct phrase contains -> high confidence
    for (const term of SUPPORT_TERMS) if (t.includes(term)) return { intent: 'support', confidence: 0.95 };
    for (const term of EXPIRY_TERMS) if (t.includes(term)) return { intent: 'expiry', confidence: 0.95 };
    for (const term of BALANCE_TERMS) if (t.includes(term)) return { intent: 'balance', confidence: 0.95 };
    for (const term of PACKAGE_TERMS) if (t.includes(term)) return { intent: 'package', confidence: 0.95 };

    // token-level fuzzy matching to catch misspellings / Nepali terms
    const tokens = t.split(/\s+/).filter(Boolean);
    let best = { intent: 'unknown', score: 0 };
    const threshold = 0.65; // lower threshold for token fuzzy
    for (const tok of tokens) {
      for (const term of EXPIRY_TERMS) {
        const s = similarityRatio(tok, term);
        if (s > best.score) best = { intent: 'expiry', score: s };
      }
      for (const term of BALANCE_TERMS) {
        const s = similarityRatio(tok, term);
        if (s > best.score) best = { intent: 'balance', score: s };
      }
      for (const term of PACKAGE_TERMS) {
        const s = similarityRatio(tok, term);
        if (s > best.score) best = { intent: 'package', score: s };
      }
      for (const term of SUPPORT_TERMS) {
        const s = similarityRatio(tok, term);
        if (s > best.score) best = { intent: 'support', score: s };
      }
    }

    if (best.score >= threshold) {
      // map score into confidence range
      const confidence = Math.min(0.95, 0.5 + best.score * 0.5);
      return { intent: best.intent, confidence };
    }

    // FAQ heuristics: question-like phrasing
    if (isLikelyFaqQuestion(text)) return { intent: 'faq', confidence: 0.6 };

    return out;
  };

  const isBalanceFollowUp = (text) => (normalizeIntent(text) || {}).intent === 'balance';
  const isExpiryFollowUp = (text) => (normalizeIntent(text) || {}).intent === 'expiry';
  const isPackagesFollowUp = (text) => (normalizeIntent(text) || {}).intent === 'package';

  const isDataConsumptionQuestion = (text) => {
    if (!text) return false;
    const t = text.trim().toLowerCase();
    // Nepali and English triggers for high data use
    const nepali = /\b(डाटा|डेटा).*(चाँडै|छिटो|चadai|chadai|sakiyo|सकियो|derai)\b/i;
    const english = /\b(data).*(fast|quick|used up|gone|consumption)\b/i;
    return nepali.test(t) || english.test(t) || /\b(मेरो डाता|mero data)\b/i.test(t);
  };

  const fetchJson = async (url) => {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
      },
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }

    if (!response.ok) {
      throw new Error((payload && payload.message) || "The assistant could not reach the service.");
    }

    return payload;
  };

  const sendIntentLog = async (payload) => {
    try {
      const csrf = getCookie('csrftoken');
      await fetch('/api/intent-log', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, csrf ? { 'X-CSRFToken': csrf } : {}),
        body: JSON.stringify(payload),
        credentials: 'same-origin',
      });
    } catch (e) {
      // ignore logging failures
    }
  };

  const buildAssistantReply = async (text) => {
    const normalized = text.trim();
    const lower = normalized.toLowerCase();

    // DEBUG LOG: incoming message and current session phone
    try { console.log('[AwajAI] incoming message:', normalized); } catch (e) {}
    try { console.log('[AwajAI] session phone:', state.sessionPhone); } catch (e) {}

    // Intent detection uses normalization + fuzzy matching for misspellings
    const detected = normalizeIntent(normalized);
    let detectedIntent = detected.intent;
    let intentConfidence = detected.confidence || 0.0;
    try { console.log('[AwajAI] detected intent:', detectedIntent, 'confidence:', intentConfidence); } catch (e) {}
    // send initial intent telemetry for tuning
    try { await sendIntentLog({ message: normalized, intent: detectedIntent, confidence: intentConfidence, route: 'detected' }); } catch (e) {}

    // ROUTING PRIORITY: 1) verified-account 2) support 3) faq 4) general 5) fallback
    // 1) Verified account requests
    if (state.sessionPhone && ['balance','expiry','package'].includes(detectedIntent)) {
      try {
        console.log('[AwajAI] routing: account_lookup (session phone present)');
      } catch (e) {}
      // Perform account lookup based on the detected intent
      try {
        const account = await fetchJson(`/api/telconnect-account?phone=${encodeURIComponent(state.sessionPhone)}`);
        const d = account.data || {};
        state.lastAccount = d;
        if (detectedIntent === 'balance') {
          return localize('account_summary', {
            name: d.customer_name,
            plan: d.plan_name,
            balance: d.balance,
            due: d.due_date,
            data: d.data_left_gb,
            minutes: d.minutes_left,
            sms: d.sms_left,
          }, detectLangFromInput(normalized));
        }
        if (detectedIntent === 'expiry') {
          return localize('due_date', { plan: d.plan_name, due: d.due_date }, detectLangFromInput(normalized));
        }
        if (detectedIntent === 'package') {
          try {
            const pkgResp = await fetchJson(`/api/package?name=${encodeURIComponent(d.plan_name)}`);
            const p = pkgResp.data || {};
            return localize('package_details', {
              name: d.customer_name,
              plan: d.plan_name,
              package_name: p.package_name,
              data_gb: p.data_gb,
              voice_minutes: p.voice_minutes,
              sms_count: p.sms_count,
            }, detectLangFromInput(normalized));
          } catch (err) {
            return localize('package_fetch_error', { name: d.customer_name, plan: d.plan_name }, detectLangFromInput(normalized));
          }
        }
      } catch (err) {
        // If account lookup fails, fall back to ask for phone — but do not drop sessionPhone
        try { console.log('[AwajAI] account lookup failed, falling back to ask_for_phone', err); } catch (e) {}
        return localize('ask_for_phone', {}, detectLangFromInput(normalized));
      }
    }

    // Determine response language based on user preference / input
    const respLang = detectLangFromInput(normalized);

    // 2) Support handling (prioritized before FAQ)
    if (detectedIntent === 'support') {
      try { console.log('[AwajAI] routing: support (prioritized)'); } catch (e) {}
      state.lastIntent = 'support';
      state.intentConfidence = intentConfidence;
      // start or continue support troubleshooting flow
      const supportState = state.supportState || { step: 0 };
      // simple conversational progression
      if (!supportState.step) {
        state.supportState = { step: 1 };
        try { await sendIntentLog({ message: normalized, intent: 'support', confidence: intentConfidence, route: 'support_start', support_state: state.supportState }); } catch (e) {}
        return respLang === 'ne'
          ? 'तपाईंको इन्टरनेट काम गरिरहेको छैन भन्ने बुझिए। कृपया निम्न जाँचहरू प्रयास गर्नुहोस्:\n1) एयरप्लेन मोड अन/अफ गर्नुहोस्.\n2) फोन रिस्टार्ट गर्नुहोस्.\n3) खुला क्षेत्रमा सर्नुहोस्।\n4) यदि वाई-फाइमा हुनुहुन्छ भने वाई-फाइ चेक गर्नुहोस्।\nयदि समस्या कायम छ भने म तपाईंलाई सपोर्टमा जोडिदिन सक्छु।'
          : 'I understand your internet is not working. Please try:\n1) Toggle airplane mode on/off.\n2) Restart your phone.\n3) Move to an open area.\n4) If on Wi‑Fi, check your router.\nIf this continues, I can connect you to customer support.';
      } else {
        // continue flow — offer escalation
        state.supportState.step += 1;
        try { await sendIntentLog({ message: normalized, intent: 'support', confidence: intentConfidence, route: 'support_continue', support_state: state.supportState }); } catch (e) {}
        return respLang === 'ne'
          ? 'म बुझ्छु समस्या जारी छ। म सपोर्ट टिकट सिर्जना गर्न सक्छु वा प्रत्यक्ष एजेन्टमा जोड्न सक्छु — के चाहनुहुन्छ?'
          : 'I understand the issue continues. I can create a support ticket or connect you to a live agent — which would you prefer?';
      }
    }

    // Handle follow-up questions that refer to the last verified account
    if (isBalanceFollowUp(normalized)) {
      // TOOL FIRST: if we have a session phone use it, otherwise ask for phone
      const phone = state.sessionPhone || null;
      if (!phone) {
        return localize("ask_for_phone", {}, respLang);
      }
      try {
        const account = await fetchJson(`/api/telconnect-account?phone=${encodeURIComponent(phone)}`);
        const d = account.data || {};
        // update cache
        state.lastAccount = d;
        return localize("account_summary", {
          name: d.customer_name,
          plan: d.plan_name,
          balance: d.balance,
          due: d.due_date,
          data: d.data_left_gb,
          minutes: d.minutes_left,
          sms: d.sms_left,
        }, respLang);
      } catch (err) {
        return localize("ask_for_phone", {}, respLang);
      }
    }

    if (isExpiryFollowUp(normalized)) {
      const phone = state.sessionPhone || null;
      if (!phone) {
        return localize("ask_for_phone", {}, respLang);
      }
      try {
        const account = await fetchJson(`/api/telconnect-account?phone=${encodeURIComponent(phone)}`);
        const d = account.data || {};
        state.lastAccount = d;
        return localize("due_date", { plan: d.plan_name, due: d.due_date }, respLang);
      } catch (err) {
        return localize("ask_for_phone", {}, respLang);
      }
    }

    if (isPackagesFollowUp(normalized)) {
      const phone = state.sessionPhone || null;
      if (!phone) {
        return localize("ask_for_phone", {}, respLang);
      }
      try {
        const account = await fetchJson(`/api/telconnect-account?phone=${encodeURIComponent(phone)}`);
        const d = account.data || {};
        state.lastAccount = d;
        if (d.plan_name) {
          try {
            const pkgResp = await fetchJson(`/api/package?name=${encodeURIComponent(d.plan_name)}`);
            const p = pkgResp.data || {};
            return localize(
              "package_details",
              {
                name: d.customer_name,
                plan: d.plan_name,
                package_name: p.package_name,
                data_gb: p.data_gb,
                voice_minutes: p.voice_minutes,
                sms_count: p.sms_count,
              },
              respLang
            );
          } catch (err) {
            return localize("package_fetch_error", { name: d.customer_name, plan: d.plan_name }, respLang);
          }
        }
        return localize("ask_what_to_know", { name: d.customer_name }, respLang);
      } catch (err) {
        return localize("ask_for_phone", {}, respLang);
      }
    }

    // SUPPORT ROUTING: support intent should bypass FAQ and non-account lookups
    if (detectedIntent === 'support') {
      try { console.log('[AwajAI] routing: support'); } catch (e) {}
      const lang = respLang;
      return lang === 'ne'
        ? 'म तपाईंलाई इन्टरनेट/नेटवर्क समस्याहरू र सामान्य ट्रबलशुटिङमा मद्दत गर्न सक्छु। कृपया आफ्नो समस्या अलि विस्तारमा लेख्नुहोस् (उदाहरण: "इन्टरनेट चल्दैन" वा "सिग्नल कमजोर")।'
        : 'I can help with internet/network issues and basic troubleshooting. Please describe the problem (for example: "internet not working" or "weak signal").';
    }

    const phoneNumber = parsePhoneNumber(normalized);
    if (phoneNumber) {
      const account = await fetchJson(`/api/telconnect-account?phone=${encodeURIComponent(phoneNumber)}`);
      const data = account.data || {};
      // store session phone and cache last verified account
      try {
        state.lastAccount = data;
        state.sessionPhone = phoneNumber;
        // Persist verified session phone so follow-ups survive reloads
        try { window.localStorage.setItem('awaj_session_phone', String(phoneNumber)); } catch (e) {}
        try { console.log('[AwajAI] verified and stored session phone:', state.sessionPhone); } catch (e) {}
        // Also persist on the server-side session so multiple clients share the state
        try { await setSessionPhoneOnServer(phoneNumber); } catch (e) {}
      } catch (e) {}
      // Prompt the user to choose what they want to know next (localized)
      const lang = detectLangFromInput(normalized);
      const verifiedMsg = localize('verified_prefix', { name: data.customer_name }, lang);
      return `${verifiedMsg} ${localize("ask_what_to_know", { name: data.customer_name }, lang)}`;
    }

    const packageQuery = parsePackageQuery(normalized);
    if (packageQuery && (lower.includes("package") || lower.includes("plan") || /\d+/.test(packageQuery))) {
      try { console.log('[AwajAI] routing: package_lookup, query:', packageQuery); } catch (e) {}
      const packageUrl = /^\d+$/.test(packageQuery)
        ? `/api/package?id=${encodeURIComponent(packageQuery)}`
        : `/api/package?name=${encodeURIComponent(packageQuery)}`;
      const packageResponse = await fetchJson(packageUrl);
      const data = packageResponse.data || {};
      const lang = detectLangFromInput(normalized);
      return localize(
        "package_details",
        {
          name: data.package_name,
          plan: data.package_name,
          package_name: data.package_name,
          data_gb: data.data_gb,
          voice_minutes: data.voice_minutes,
          sms_count: data.sms_count,
        },
        lang
      );
    }

    // Data consumption specific handling
    if (isDataConsumptionQuestion(normalized)) {
      const respLang = detectLangFromInput(normalized);
      return `${localize("high_data_explain", {}, respLang)} ${localize("data_fast_tips", {}, respLang)}`;
    }

    // Attempt FAQ search proactively for likely FAQ-style queries, but don't override detected account/support intents
    if (isLikelyFaqQuestion(normalized) && !['balance','expiry','package','support'].includes(detectedIntent)) {
      try { console.log('[AwajAI] routing: proactive_faq_search'); } catch (e) {}
      try {
        const faqResponse = await fetchJson(`/api/faq?q=${encodeURIComponent(parseFaqQuery(normalized))}`);
        const firstResult = (faqResponse.data && faqResponse.data.results && faqResponse.data.results[0]) || null;
        if (firstResult) {
          const lang = detectLangFromInput(normalized);
          return localize("faq_result_prefix", { question: firstResult.question, answer: firstResult.answer }, lang);
        }
      } catch (err) {
        // fall through to generic handling
      }
    }

    if (lower.includes("faq") || lower.includes("help") || lower.includes("how") || lower.includes("what") || lower.includes("why") || lower.includes("when") || lower.includes("where")) {
      try { console.log('[AwajAI] routing: explicit_faq_search'); } catch (e) {}
      const faqResponse = await fetchJson(`/api/faq?q=${encodeURIComponent(parseFaqQuery(normalized))}`);
      const firstResult = (faqResponse.data && faqResponse.data.results && faqResponse.data.results[0]) || null;
      if (firstResult) {
        const lang = detectLangFromInput(normalized);
        return localize("faq_result_prefix", { question: firstResult.question, answer: firstResult.answer }, lang);
      }
      const lang = detectLangFromInput(normalized);
      return localize("help_prompt", {}, lang);
    }

    // Prefer a concise telecom-specific question instead of a generic fallback.
    const lang = detectLangFromInput(normalized);
    return lang === "ne"
      ? "म तपाईंको ब्यालेन्स, प्याकेज वा म्याद सम्बन्धी जानकारी दिन सक्छु। कृपया आफ्नो प्रश्न अलि स्पष्ट रूपमा लेख्नुहोस्।"
      : "I can provide your balance, package, or expiry details — please clarify your question.";
  };

  const handleAssistantResponse = async (messageText) => {
    appendBubble("user", "You", messageText);
    setStatus("Thinking...");
    const loadingBubble = appendBubble("assistant", "Awaj AI", "Working on that now.");

    try {
      const reply = await buildAssistantReply(messageText);
      loadingBubble.remove();
      appendBubble("assistant", "Awaj AI", reply);
      setStatus(state.voiceEnabled ? "Voice mode active" : "Text mode active");
      speak(reply);
    } catch (error) {
      loadingBubble.remove();
      const fallbackReply = error instanceof Error ? error.message : "Something went wrong while processing that request.";
      appendBubble("assistant", "Awaj AI", fallbackReply);
      setStatus("Ready for another question");
      speak(fallbackReply);
    }
  };

  const startVoiceRecognition = () => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!Recognition) {
      appendBubble("assistant", "Awaj AI", "Speech recognition is not available in this browser, so please keep using the keyboard.");
      setStatus("Voice input unavailable");
      setListeningState(false);
      return;
    }

    if (state.listening) {
      return;
    }

    if (!state.recognition) {
      state.recognition = new Recognition();
      // Set recognition language based on preference (auto uses en-US by default)
      state.recognition.lang = state.preferredLang === "ne" ? "ne-NP" : "en-US";
      state.recognition.interimResults = false;
      state.recognition.maxAlternatives = 1;

      state.recognition.onresult = (event) => {
        const spokenText = event.results[0][0].transcript;
        inputNode.value = spokenText;
        handleAssistantResponse(spokenText);
      };

      state.recognition.onerror = () => {
        setStatus("Voice input could not start");
        setListeningState(false);
      };

      state.recognition.onend = () => {
        setListeningState(false);
        setStatus(state.voiceEnabled ? "Voice mode active" : "Text mode active");
      };
    }

    try {
      setListeningState(true);
      setStatus("Listening...");
      // Ensure recognition language aligns with user preference when starting
      if (state.recognition && typeof state.recognition.lang !== "undefined") {
        state.recognition.lang = state.preferredLang === "ne" ? "ne-NP" : "en-US";
      }
      state.recognition.start();
    } catch (error) {
      setListeningState(false);
      setStatus("Voice input could not start");
    }
  };

  formNode.addEventListener("submit", (event) => {
    event.preventDefault();
    const messageText = inputNode.value.trim();

    if (!messageText) {
      return;
    }

    inputNode.value = "";
    handleAssistantResponse(messageText);
  });

  voiceToggleButton.addEventListener("click", () => {
    state.voiceEnabled = !state.voiceEnabled;
    voiceToggleButton.textContent = state.voiceEnabled ? "Voice mode on" : "Voice mode off";
    voiceToggleButton.setAttribute("aria-pressed", String(state.voiceEnabled));
    setStatus(state.voiceEnabled ? "Voice mode active" : "Text mode active");
  });
  const langToggleButton = document.getElementById("lang-toggle-button");
  if (langToggleButton) {
    langToggleButton.addEventListener("click", () => {
      cycleLang();
      // If recognition is active, update its language to the newly selected preference
      if (state.recognition && typeof state.recognition.lang !== "undefined") {
        state.recognition.lang = state.preferredLang === "ne" ? "ne-NP" : "en-US";
      }
    });
  }

  voiceInputButton.addEventListener("click", startVoiceRecognition);

  promptButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const prompt = button.dataset.prompt || "";
      // send immediately instead of only filling the input
      handleAssistantResponse(prompt);
    });
  });
})();
