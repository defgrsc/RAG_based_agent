(function () {
  const API_URL = window.NTHU_CHAT_API_URL || `${window.location.origin}/chat`;
  const TRANSLATE_URL = window.NTHU_TRANSLATE_API_URL || API_URL.replace(/\/chat\/?$/, "/translate");
  const SESSION_CLEAR_URL = API_URL.replace(/\/chat\/?$/, "/session/clear");
  const widget = document.querySelector(".chat-widget");
  const panel = document.querySelector(".chat-panel");
  const body = document.querySelector("[data-chat-body]");
  const form = document.querySelector("[data-chat-form]");
  const input = document.querySelector("[data-chat-input]");
  const openButton = document.querySelector('[data-action="open"]');
  const closeButton = document.querySelector('[data-action="close"]');
  const clearButton = document.querySelector('[data-action="clear"]');
  const languageButton = document.querySelector('[data-action="language"]');
  const initialBodyHtml = body.innerHTML;

  const translations = {
    "zh-Hant": { pageTitle: "清大網路客服 Widget Prototype", demoPageLabel: "網站範例頁面", demoContentLabel: "範例內容", heroTitle: "國立清華大學網路系統組", heroDescription: "這是一個用來測試右下角 AI 客服 bubble 的暫時頁面。正式導入時，只需要把 widget 相關的 HTML、CSS、JavaScript 搬到目標網站即可。", commonServices: "常用服務", commonServicesDescription: "校園無線網路、宿舍網路、VPN、電子郵件與資安相關服務。", serviceNotice: "服務提醒", serviceNoticeDescription: "右下角的客服 bubble 可用來查詢清大網路服務資訊與相關來源。", nudge: "清大網路問題可以問我", panelLabel: "清大網路客服對話框", chatTitle: "清大網路客服", clear: "清除", clearLabel: "清除聊天室", closeLabel: "關閉對話框", welcome: "請問我清大無線網路、宿網、VPN、信箱等問題。", promptsLabel: "建議問題", promptWifi: "校園無線網路怎麼使用？", promptDormApply: "宿舍網路怎麼申請？", promptWifiPage: "為什麼我進不去申請無線網路的網頁？", promptDormIssue: "為什麼我連不上宿網？", inputLabel: "輸入問題", inputPlaceholder: "輸入清大網路相關問題...", sendLabel: "送出訊息", openLabel: "開啟清大網路客服", typingLabel: "AI 正在回覆", sources: "來源", collapseSources: "收合來源", sourceFallback: "來源", serviceError: "服務目前無法回應，請稍後再試。", emptyAnswer: "沒有取得回答。", connectionError: "服務目前無法連線，請稍後再試。", translating: "翻譯中", editMessage: "編輯訊息", saveEdit: "送出", cancelEdit: "取消", languageButton: "EN", languageButtonLabel: "Switch to English" },
    en: { pageTitle: "NTHU Network Support Widget Prototype", demoPageLabel: "Demo page", demoContentLabel: "Demo content", heroTitle: "NTHU Network Systems Division", heroDescription: "This temporary page demonstrates the AI support widget in the lower-right corner. To deploy it, move the widget HTML, CSS, and JavaScript to the target website.", commonServices: "Common Services", commonServicesDescription: "Campus Wi-Fi, dormitory networks, VPN, email, and information security services.", serviceNotice: "Service Tip", serviceNoticeDescription: "Use the support bubble in the lower-right corner to ask about NTHU network services and view relevant sources.", nudge: "Ask me about NTHU network services", panelLabel: "NTHU network support chat", chatTitle: "NTHU Network Support", clear: "Clear", clearLabel: "Clear chat", closeLabel: "Close chat", welcome: "Ask me about NTHU Wi-Fi, dormitory networks, VPN, email, and more.", promptsLabel: "Suggested questions", promptWifi: "How do I use NTHU campus Wi-Fi?", promptDormApply: "How do I apply for the NTHU dormitory network?", promptWifiPage: "Why can’t I open the NTHU Wi-Fi application page?", promptDormIssue: "Why can’t I connect to the NTHU dormitory network?", inputLabel: "Enter a question", inputPlaceholder: "Ask about NTHU network services...", sendLabel: "Send message", openLabel: "Open NTHU network support", typingLabel: "AI is replying", sources: "Sources", collapseSources: "Hide sources", sourceFallback: "Source", serviceError: "The service is unavailable. Please try again later.", emptyAnswer: "No answer was returned.", connectionError: "Unable to connect to the service. Please try again later.", translating: "Translating", editMessage: "Edit message", saveEdit: "Send", cancelEdit: "Cancel", languageButton: "中文", languageButtonLabel: "切換至繁體中文" }
  };

  const commonMessageTranslations = {
    en: {
      "校園無線網路怎麼使用？": "How do I use NTHU campus Wi-Fi?",
      "宿舍網路怎麼申請？": "How do I apply for the NTHU dormitory network?",
      "那如果我換宿了呢？": "What if I change dorms?",
      "那如果我換宿了呢": "What if I change dorms?",
      "為什麼我進不去申請無線網路的網頁？": "Why can’t I open the NTHU Wi-Fi application page?",
      "為什麼我連不上宿網？": "Why can’t I connect to the NTHU dormitory network?",
      "清大信箱怎麼申請？": "How do I apply for NTHU email?",
      "gapp 的那個信箱怎麼申請": "How do I apply for the gapp email account?",
      "gapp 的那個信箱怎麼申請？": "How do I apply for the gapp email account?",
      "要怎麼設定學校的VPN": "How do I set up the NTHU VPN?",
      "要怎麼設定學校的VPN？": "How do I set up the NTHU VPN?",
      "分享器要怎麼連宿舍網路？": "How do I connect a router to the dormitory network?",
      "要怎麼設定宿舍網路？": "How do I set the dormitory network IP?",
      "Wi-Fi 要怎麼申請？": "How do I apply for Wi-Fi?",
      "Wi-Fi 怎麼申請？": "How do I apply for Wi-Fi?",
      "Wi-Fi 怎麼申請": "How do I apply for Wi-Fi?",
      "台積館有網路嗎？": "Is there Wi-Fi at the TSMC Building?",
      "台積館有網路嗎": "Is there Wi-Fi at the TSMC Building?",
      "那水木呢？": "What about Shui Mu Life Center?",
      "那水木呢": "What about Shui Mu Life Center?",
      "紅吱吱牛排有網路嗎？": "Does Red Zhi Zhi steak have Wi-Fi?",
      "紅吱吱牛排有網路嗎": "Does Red Zhi Zhi steak have Wi-Fi?",
      "那梅園呢？": "What about Mei Garden?",
      "那梅園呢": "What about Mei Garden?",
      "那 VPN 也要開嗎？": "Do I also need to enable VPN?",
      "VPN 也要一起開嗎？": "Do I also need to enable VPN?",
      "如果我換宿了呢？": "What if I moved dorms?",
      "我之前住新齋，後來換到儒齋，這會有關嗎？": "I moved from Xin Zhai to Ru Zhai. Could that be related?",
      "可是我照著你的步驟做還是不行欸": "I followed your steps, but it still does not work.",
      "download folder 22.7R2.8 是什麼意思？": "What does download folder 22.7R2.8 mean?",
      "password 要填什麼？": "What password should I enter?",
      "如果我在水木訊號很差呢？": "What if the Wi-Fi signal at Shui Mu is poor?",
      "我人在風雲樓": "I'm in Fengyun Building.",
      "剛剛還可以，但現在 Wi-Fi 很卡": "It worked earlier, but the Wi-Fi is very slow now.",
      "我照著做還是不行": "I followed the steps, but it still does not work.",
      "VPN 軟體的帳號我知道了 但密碼要填什麼": "I know the VPN client account, but what password should I enter?",
      "密碼要填什麼？": "What password should I enter?",
      "密碼要填什麼": "What password should I enter?",
      "下載網址裡面的資料夾都是數字，接下來要點哪個？": "The folders in the download URL are all numbers. Which one should I click next?",
      "水木有網路嗎？": "Does Shui Mu have Wi-Fi?",
      "那風雲樓勒？": "What about Fengyun Building?",
      "紅吱吱牛排呢？": "What about Red Zhi Zhi Steak?",
      "小吃部有網路嗎？": "Does the cafeteria have Wi-Fi?",
      "最近在那邊 Wi-Fi 很卡": "The Wi-Fi is very slow there recently.",
      "我在圖書館連不到網路": "I cannot connect to the network in the library.",
      "那紅吱吱牛排呢？": "What about Red Zhi Zhi steak?",
      "那紅吱吱牛排呢": "What about Red Zhi Zhi steak?",
      "那 VPN 呢？": "What about VPN?",
      "那 VPN 呢": "What about VPN?",
      "那宿網呢？": "What about DormNet?",
      "那宿網呢": "What about DormNet?",
      "Wi-Fi 連不上怎麼辦？": "What should I do if I cannot connect to Wi-Fi?",
      "Wi-Fi 連不上怎麼辦": "What should I do if I cannot connect to Wi-Fi?",
      "那要去哪裡申請？": "Where do I apply for it?",
      "那要去哪裡申請": "Where do I apply for it?",
      "照你的方法做還是不行": "I followed your method but it still does not work.",
      "那我在圖書館也是一樣嗎？": "Is it the same if I am in the library?",
      "那我在圖書館也是一樣嗎": "Is it the same if I am in the library?",
      "那如果我在校內還是不行？": "What if I'm on campus and it still does not work?",
      "那如果我在校內還是不行": "What if I'm on campus and it still does not work?",
      "我人在校外，那怎麼辦？": "I'm off campus. What should I do?",
      "我人在校外，那怎麼辦": "I'm off campus. What should I do?",
      "我是儒齋學生": "I am a Ru Zhai student.",
      "最近網路很爛": "The network has been very bad recently.",
      "如果是網路孔壞掉怎麼辦？": "What if the network wall port is broken?",
      "清大信箱怎麼申請？": "How do I apply for NTHU email?",
      "nthu-cc 使用": "How do I use nthu-cc?",
      "登入頁一直跳不出來": "The login page does not appear.",
      "那學生信箱格式是什麼？": "What is the student email address format?",
      "那如果是 eduroam 登入失敗呢？": "What if eduroam login fails?",
      "噢然後是從上禮拜開始的，可以幫我看看有什麼問題嗎？": "It started last week. Could you help me check what might be wrong?",
      "上禮拜開始的，可以幫我看看可能是什麼問題嗎？": "It started last week. Could you help me check what might be wrong?",
      "為什麼我連不上宿網？": "Why can't I connect to DormNet?",
      "那 IP 要怎麼設定？": "How should I set the IP?",
      "我要連哪個 Wi-Fi 比較好？": "Which Wi-Fi should I connect to?",
      "台大網路很差可能是什麼原因？": "Why might the NTU network be poor?"
    },
    "zh-Hant": {
      "How do I use NTHU campus Wi-Fi?": "校園無線網路怎麼使用？",
      "How do I apply for the NTHU dormitory network?": "宿舍網路怎麼申請？",
      "How do I apply for campus Wi-Fi?": "Wi-Fi 怎麼申請？",
      "How do I apply for Wi-Fi?": "Wi-Fi 怎麼申請？",
      "How to Apply for Wi-Fi?": "Wi-Fi 怎麼申請？",
      "How do I use nthu-cc?": "那 nthu-cc 要怎麼用？",
      "The login page does not appear.": "登入頁一直跳不出來",
      "I am a Ru Zhai student.": "我是儒齋學生",
      "The network has been very bad recently.": "最近網路很爛",
      "What if the network wall port is broken?": "如果是網路孔壞掉怎麼辦？",
      "Is there Wi-Fi at the TSMC Building?": "台積館有網路嗎？",
      "Is there Wi-Fi at the TSMC Museum?": "台積館有網路嗎？",
      "What about Shui Mu Life Center?": "那水木呢？",
      "What about Shuimu?": "那水木呢？",
      "Does Red Zhi Zhi steak have Wi-Fi?": "紅吱吱牛排有網路嗎？",
      "Does Hong Zhizhi Steak have Wi-Fi?": "紅吱吱牛排有網路嗎？",
      "What about Mei Garden?": "那梅園呢？",
      "What about Meiyuan?": "那梅園呢？",
      "How do I apply for campus WiFi?": "Wi-Fi 怎麼申請？",
      "Why can't I access the wireless network application page?": "為什麼我進不去申請無線網路的網頁？",
      "What if I change dorms?": "如果我換宿了呢？",
      "Why can’t I open the NTHU Wi-Fi application page?": "為什麼我進不去申請無線網路的網頁？",
      "Why can’t I connect to the NTHU dormitory network?": "為什麼我連不上宿網？",
      "How do I apply for NTHU email?": "清大信箱怎麼申請？",
      "How do I apply for the gapp email account?": "gapp 的那個信箱怎麼申請？",
      "How do I set up the NTHU VPN?": "要怎麼設定學校的VPN？",
      "How do I connect a router to the dormitory network?": "分享器要怎麼連宿舍網路？",
      "How do I set the dormitory network IP?": "要怎麼設定宿舍網路？",
      "How do I use eduroam at another university?": "如何在其他大學使用 eduroam？",
      "What username and password should I enter?": "我要輸入什麼帳號和密碼？",
      "I know the username, but what password should I enter?": "我知道帳號了，但密碼要填什麼？",
      "I know the VPN client account, but what password should I enter?": "我知道 VPN 軟體的帳號，但密碼要填什麼？",
      "The download folders are numbers like 22.7R2.8. What do they mean?": "下載資料夾像 22.7R2.8 這種數字是什麼意思？",
      "The folders in the download URL are all numbers. Which one should I click next?": "下載網址裡面的資料夾都是數字，接下來要點哪個？",
      "Does Shui Mu have Wi-Fi?": "水木有網路嗎？",
      "What about Fengyun Building?": "那風雲樓呢？",
      "What if I moved dorms?": "如果我換宿了呢？",
      "I moved from Xin Zhai to Ru Zhai. Could that be related?": "我之前住新齋，後來換到儒齋，這會有關嗎？",
      "I followed your steps, but it still does not work.": "可是我照著你的步驟做還是不行欸",
      "What does download folder 22.7R2.8 mean?": "download folder 22.7R2.8 是什麼意思？",
      "What password should I enter?": "密碼要填什麼？",
      "What should I enter for the password?": "密碼要填什麼？",
      "How should I set the IP?": "那 IP 要怎麼設定？",
      "The Wi-Fi is unstable there.": "那裡的 Wi-Fi 不穩定。",
      "What if the Wi-Fi signal at Shui Mu is poor?": "如果我在水木訊號很差呢？",
      "I'm in the library.": "我人在圖書館。",
      "I'm in Fengyun Building.": "我人在風雲樓。",
      "The Wi-Fi login page does not appear.": "Wi-Fi 登入頁跳不出來。",
      "I followed your steps but it still does not work.": "我照著你的步驟做但還是不行。",
      "I followed the steps, but it still does not work.": "我照著做還是不行。",
      "What about Red Zhi Zhi steak?": "那紅吱吱牛排呢？",
      "Does the cafeteria have Wi-Fi?": "小吃部有網路嗎？",
      "The Wi-Fi is very slow there recently.": "最近在那邊 Wi-Fi 很卡。",
      "I cannot connect to the network in the library.": "我在圖書館連不到網路。",
      "What about DormNet?": "那宿網呢？",
      "What about VPN?": "那 VPN 呢？",
      "What about the Hong Zhi Zhi steak?": "那紅吱吱牛排呢？",
      "What about the Hong Zhizhi steak?": "那紅吱吱牛排呢？",
      "How do I apply for the gapp email account?": "gapp 的那個信箱怎麼申請？",
      "What is the student email address format?": "那學生信箱格式是什麼？",
      "What about the VPN?": "那 VPN 呢？",
      "What should I do if I cannot connect to Wi-Fi?": "Wi-Fi 連不上怎麼辦？",
      "Where do I apply for it?": "那要去哪裡申請？",
      "I followed your method but it still does not work.": "照你的方法做還是不行。",
      "Is it the same if I am in the library?": "那我在圖書館也是一樣嗎？",
      "What if I'm on campus and it still does not work?": "那如果我在校內還是不行？",
      "I'm off campus. What should I do?": "我人在校外，那怎麼辦？",
      "I am a Ru Zhai student.": "我是儒齋學生。",
      "The network has been very bad recently.": "最近網路很爛。",
      "What if the network wall port is broken?": "如果是網路孔壞掉怎麼辦？",
      "I live in Ru Zhai.": "我住在儒齋。",
      "DormNet has been very bad recently.": "最近宿網很爛。",
      "It started last week. Could you help me check what might be wrong?": "上禮拜開始的，可以幫我看看可能是什麼問題嗎？",
      "What if the wall port is broken?": "如果網路孔壞掉怎麼辦？",
      "The Wi-Fi is very slow there.": "那裡 Wi-Fi 很慢。",
      "Which Wi-Fi should I connect to?": "我應該連哪個 Wi-Fi？",
      "The download folders are all numbers. What do they mean?": "下載資料夾都是數字，代表什麼意思？",
      "I know the VPN account, but what password should I enter?": "我知道 VPN 帳號，但密碼要填什麼？",
      "How do I apply for the gapp account?": "gapp 帳號怎麼申請？"
    }
  };

  function localWirelessQualityTranslation(text, targetLanguage) {
    const value = String(text || "").trim();
    const zhMatch = value.match(/^如果你在(.+?)連不到網路，或最近覺得網路很差，可以先從 Wi-Fi 名稱、訊號環境、認證與 IP 狀態這幾個方向檢查。/);
    if (targetLanguage === "en" && zhMatch) {
      const placeNames = { "圖書館": "the library", "風雲樓": "Fengyun Building", "水木生活中心": "Shui Mu Life Center", "水木": "Shui Mu Life Center" };
      const place = placeNames[zhMatch[1]] || zhMatch[1];
      return `If NTHU campus Wi-Fi at ${place} is slow, unstable, or cannot connect, first check the Wi-Fi name, signal environment, authentication status, and IP settings.

**Check the connection source**
1. Make sure you are connected to the correct NTHU Wi-Fi. On campus, you can use \`nthu-cc\`, \`TANetRoaming\`, \`nthupeap\`, or \`eduroam\`.
2. If you are connected to a similar-looking, weak, or non-NTHU Wi-Fi name, the connection may be unstable.

**Check signal and location**
1. If you are far from an access point, behind walls, or in a crowded area, the signal quality may drop.
2. Move to a hallway, public area, or a spot with stronger signal and test again.

**Check authentication and IP status**
1. For \`nthu-cc\` or \`TANetRoaming\`, open a browser and confirm whether you need to log in again.
2. For \`nthupeap\` or \`eduroam\`, forget the saved Wi-Fi setting and reconnect.
3. Wi-Fi IP settings should normally use automatic IP assignment, not a fixed IP.

**Get help**
If the same location remains slow or unusable, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, time, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless
https://net.nthu.edu.tw/netsys/en:faq:wlan_range`;
    }
    return "";
  }

  function localKnownAnswerTranslation(text, targetLanguage) {
    const value = String(text || "").trim();
    if (targetLanguage === "en" && (value.startsWith("無線網路申請頁無法進入時") || value.startsWith("無線網路帳號申請頁面無法進入時"))) {
      return `If the wireless LAN application page will not open, check the following items first.

**Check whether you are using an NTHU campus IP**
1. The application page must be accessed from an NTHU campus IP address.
2. If you are off campus, connect to the NTHU VPN first and then try opening the page again.

**If you are already on campus but still cannot open it**
1. Log in to the Academic Information System again.
2. In the left menu, open the Computer and Communication Center related services, then enter the Network Systems Division online service.
3. Click the Network Systems Division online service login link again.
4. If you see \`Cannot get checksum or expired\`, the link has likely expired after about 2 minutes. Generate a new link and try again.
5. If you see \`IP mismatch\`, the current source IP differs from the one used when logging in. Reconnect using a stable network and log in again.

**Get help**
If it still fails, contact wlan@cc.nthu.edu.tw with your device OS, location, current network source, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp`;
    }
    if (targetLanguage === "zh-Hant" && value.startsWith("If the wireless LAN application page will not open")) {
      return `無線網路申請頁無法進入時，請依序確認以下狀況：

**確認是否從校內 IP 連線**
1. 申請頁面僅限校內 IP 使用。
2. 若人在校外，請先連上學校 VPN 後再嘗試開啟。

**若已從校內連線但仍無法進入**
1. 重新登入校務資訊系統。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 重新點選右方出現的「登入網路系統組線上服務」連結。
4. 若出現 \`Cannot get checksum or expired\`，通常表示連結已超過約 2 分鐘有效時間，請重新產生連結。
5. 若出現 \`IP mismatch\`，表示目前來源 IP 與登入校務資訊系統時不同，請確認網路環境後重新登入。

**尋求幫助**
若仍無法進入，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供裝置系統、所在位置、目前網路來源、錯誤訊息與截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/wireless:application:ccxp`;
    }
    return "";
  }

  function localMessageTranslation(text, targetLanguage) {
    const normalized = String(text || "").replace(/\s+/g, " ").trim();
    return commonMessageTranslations[targetLanguage]?.[normalized] || localKnownAnswerTranslation(text, targetLanguage) || localWirelessQualityTranslation(text, targetLanguage) || "";
  }

  let language = "zh-Hant";
  function newChatSessionId() {
    return window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  let chatSessionId = newChatSessionId();

  function t(key) { return translations[language][key] || key; }

  function applyLanguage() {
    document.documentElement.lang = language;
    document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => { element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel)); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => { element.placeholder = t(element.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-prompt-key]").forEach((button) => { button.textContent = t(button.dataset.promptKey); });
    languageButton.querySelector("[data-language-label]").textContent = t("languageButton");
    languageButton.setAttribute("aria-label", t("languageButtonLabel"));
    document.documentElement.dataset.language = language;
    document.querySelectorAll(".sources").forEach((wrapper) => {
      const toggle = wrapper.querySelector(".source-toggle");
      const count = wrapper.dataset.sourceCount || "0";
      if (toggle) {
        toggle.textContent = wrapper.dataset.expanded === "true" ? t("collapseSources") : `${t("sources")} ${count}`;
      }
    });
    updateEditableMessages();
  }

  let isSending = false;
  let currentRequest = null;
  let currentTyping = null;
  let requestSeq = 0;
  let editingRow = null;
  const chatHistory = [];
  const MAX_HISTORY_ITEMS = 8;
  const LANGUAGE_SWITCH_FALLBACK_MS = 300;
  const LANGUAGE_SWITCH_RECENT_ROWS = 12;

  function isVisibleMessageRow(row) {
    const bodyRect = body.getBoundingClientRect();
    const rowRect = row.getBoundingClientRect();
    return rowRect.bottom >= bodyRect.top - 80 && rowRect.top <= bodyRect.bottom + 160;
  }

  function prioritizeLanguageRows(rows) {
    const priority = [];
    const rest = [];
    rows.forEach((row, index) => {
      if (isVisibleMessageRow(row) || index >= rows.length - LANGUAGE_SWITCH_RECENT_ROWS) {
        priority.push(row);
      } else {
        rest.push(row);
      }
    });
    return { priority, rest };
  }

  function rememberMessage(role, content) {
    if (typeof content !== "string") {
      return;
    }
    const normalized = content.replace(/\s+/g, " ").trim();
    if (!normalized) {
      return;
    }

    chatHistory.push({ role, content: normalized.slice(0, 800) });
    while (chatHistory.length > MAX_HISTORY_ITEMS) {
      chatHistory.shift();
    }
  }


  function responseErrorMessage(data, fallback) {
    const detail = data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail.message === "string" && detail.message.trim()) {
      return detail.message;
    }
    return fallback;
  }

  function setOpen(open) {
    widget.dataset.open = String(open);
    panel.setAttribute("aria-hidden", String(!open));

    if (open) {
      window.setTimeout(() => input.focus(), 120);
    } else {
      openButton.focus();
    }
  }

  function scrollToBottom() {
    body.scrollTop = body.scrollHeight;
  }

  function scrollToMessageStart(row) {
    const bodyTop = body.getBoundingClientRect().top;
    const rowTop = row.getBoundingClientRect().top;
    body.scrollTop += rowTop - bodyTop - 12;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderInlineMarkdown(text) {
    return escapeHtml(text || "")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s<>)）]+)\)/g, "<a href=$2 target=_blank rel=noreferrer>$1</a>")
      .replace(/(^|[\s：:])(https?:\/\/[^\s<>)）。，、；;]+)(?=$|[\s<>)）。，、；;])/g, "$1<a href=$2 target=_blank rel=noreferrer>$2</a>")
      .replace(/\*\*/g, "");
  }

  function flushList(parts, listState) {
    if (!listState.type) {
      return;
    }

    const startAttr = listState.type === "ol" && listState.start && listState.start > 1 ? ` start="${listState.start}"` : "";
    parts.push(`<${listState.type}${startAttr}>${listState.items.join("")}</${listState.type}>`);
    listState.type = null;
    listState.start = null;
    listState.items = [];
  }

  const headingTranslations = {
    "zh-Hant": {
      "On-campus Use": "校內使用", "Off-campus Roaming": "外校漫遊", "Apply for a Wireless LAN Account": "申請無線網路帳號",
      "VPN Account Application and Activation": "VPN 帳號申請與啟用", "VPN Connection Setup": "VPN 連線設定",
      "Apply for DormNet": "申請宿舍網路", "Apply for a DormNet Account": "申請宿網帳號", "Application": "申請方式",
      "Device Setup and Connection": "裝置設定與連線", "DormNet IP Settings": "宿網 IP 設定", "Network Coverage": "網路涵蓋情況",
      "Browser-based Login": "瀏覽器登入（Web-based 認證）", "Automatic Wi-Fi Login": "WiFi 登入（設定一次即可）（802.1X + PEAP）",
      "Get Help": "尋求幫助", "Contact for Help": "尋求幫助", "Seek Assistance": "尋求幫助", "For details": "詳細可參考", "For more details, please refer to": "詳細可參考", "Check Status": "查狀態",
      "Cross-check": "交叉測試", "Authentication Issue": "認證問題", "IP Issue": "IP 問題"
    },
    en: {
      "校內使用": "On-campus Use", "外校漫遊": "Off-campus Roaming", "到外校漫遊": "Off-campus Roaming", "申請無線網路帳號": "Apply for a Wireless LAN Account",
      "VPN 帳號申請與啟用": "VPN Account Application and Activation", "VPN 連線設定": "VPN Connection Setup",
      "申請宿舍網路": "Apply for DormNet", "申請學生宿舍網路帳號": "Apply for a DormNet Account", "申請宿網帳號": "Apply for a DormNet Account",
      "申請方式": "Application", "裝置設定與連線": "Device Setup and Connection", "宿網 IP 設定": "DormNet IP Settings", "網路涵蓋情況": "Network Coverage",
      "瀏覽器登入（Web-based 認證）": "Browser-based Login", "Web-based 認證": "Browser-based Login",
      "自動登入（設定一次即可）（802.1X + PEAP）": "Automatic Wi-Fi Login", "WiFi 登入（設定一次即可）（802.1X + PEAP）": "Automatic Wi-Fi Login",
      "802.1X + PEAP 認證": "Automatic Wi-Fi Login", "尋求協助": "Get Help", "尋求幫助": "Get Help", "詳細可參考": "For details",
      "Seek Assistance": "Get Help", "Contact for Help": "Get Help", "For more details, please refer to": "For details", "查狀態": "Check Status", "交叉測試": "Cross-check", "認證問題": "Authentication Issue", "IP 問題": "IP Issue"
    }
  };

  function localizeHeading(line) {
    return headingTranslations[language][line.replace(/[:：]$/, "")] || line;
  }

  function isPrimaryHeading(line) {
    return /^(校內使用|外校漫遊|到外校漫遊|申請無線網路帳號|VPN 帳號申請與啟用|VPN 連線設定|申請宿舍網路|申請學生宿舍網路帳號|申請宿網帳號|申請方式|裝置設定與連線|宿網 IP 設定|網路涵蓋情況|小吃部|紅吱吱牛排|On-campus Use|Off-campus Roaming|Apply for a Wireless LAN Account|VPN Account Application and Activation|VPN Connection Setup|Apply for DormNet|Apply for a DormNet Account|Application|Device Setup and Connection|DormNet IP Settings|Network Coverage)$/.test(line);
  }

  function isSecondaryHeading(line) {
    return /^(瀏覽器登入（Web-based 認證）|自動登入（設定一次即可）（802\.1X \+ PEAP）|WiFi 登入（設定一次即可）（802\.1X \+ PEAP）|Web-based 認證|802\.1X \+ PEAP 認證|尋求協助|尋求幫助|詳細可參考|第一段[:：].+|第二段[:：].+|情況[一二三四][:：].+|查狀態|交叉測試|認證問題|IP 問題|Browser-based Login|Automatic Wi-Fi Login|Get Help|Contact for Help|Seek Assistance|For details|For more details, please refer to|Check Status|Cross-check|Authentication Issue|IP Issue)$/.test(line);
  }

  function renderHeadingText(line) {
    line = localizeHeading(line);
    if (
      line === "WiFi 登入（設定一次即可）（802.1X + PEAP）" ||
      line === "自動登入（設定一次即可）（802.1X + PEAP）"
    ) {
      return 'WiFi 登入（設定一次即可）<span class="heading-break">（802.1X + PEAP）</span>';
    }
    return renderInlineMarkdown(line);
  }

  function cleanHeadingText(text) {
    return String(text || "")
      .replace(/^\d+[.．、]\s*/, "")
      .replace(/^[一二三四五六七八九十]+[.．、]\s*/, "")
      .trim();
  }

  function renderAnswer(text) {
    const parts = [];
    const listState = { type: null, start: null, items: [] };
    if (typeof text !== "string") {
      throw new TypeError("Chat response answer must be a string");
    }
    const lines = text.split(/\r?\n/);
    let inReferences = false;

    function closeReferences() {
      if (inReferences) {
        flushList(parts, listState);
        parts.push("</div>");
        inReferences = false;
      }
    }

    lines.forEach((rawLine) => {
      const line = rawLine.trim();

      if (!line) {
        return;
      }

      const heading = line.match(/^(#{2,4})\s+(.+)$/);
      if (heading) {
        closeReferences();
        flushList(parts, listState);
        const level = heading[1].length === 2 ? 3 : 4;
        parts.push(`<h${level}>${renderHeadingText(cleanHeadingText(heading[2]))}</h${level}>`);
        return;
      }

      const strongOnly = line.match(/^\*\*(.+?)\*\*$/);
      const headingLine = cleanHeadingText(strongOnly ? strongOnly[1] : line);
      if (/^(詳細可參考|For details|For more details, please refer to)[:：]?$/.test(headingLine)) {
        closeReferences();
        flushList(parts, listState);
        parts.push(`<div class="references"><p>${language === "en" ? "For details" : "詳細可參考"}</p>`);
        inReferences = true;
        return;
      }

      if (isPrimaryHeading(headingLine)) {
        closeReferences();
        flushList(parts, listState);
        parts.push(`<h3>${renderHeadingText(headingLine)}</h3>`);
        return;
      }

      if (isSecondaryHeading(headingLine)) {
        closeReferences();
        flushList(parts, listState);
        parts.push(`<h4>${renderHeadingText(headingLine)}</h4>`);
        return;
      }

      const standaloneUrl = line.match(/^https?:\/\/[^\s]+$/);
      if (standaloneUrl) {
        flushList(parts, listState);
        parts.push(`<p class="standalone-url">${renderInlineMarkdown(line)}</p>`);
        return;
      }

      const ordered = line.match(/^(\d+)\.\s+(.+)$/);
      if (ordered) {
        if (listState.type !== "ol") {
          flushList(parts, listState);
          listState.type = "ol";
          listState.start = Number(ordered[1]);
        }
        listState.items.push(`<li>${renderInlineMarkdown(ordered[2])}</li>`);
        return;
      }

      const unordered = line.match(/^[-*]\s+(.+)$/);
      if (unordered) {
        if (listState.type !== "ul") {
          flushList(parts, listState);
          listState.type = "ul";
        }
        listState.items.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`);
        return;
      }

      flushList(parts, listState);
      parts.push(`<p>${renderInlineMarkdown(line)}</p>`);
    });

    closeReferences();
    flushList(parts, listState);
    return parts.join("");
  }

  function clearBackendSessionCache() {
    const payload = JSON.stringify({ session_id: chatSessionId });
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(SESSION_CLEAR_URL, blob);
    } else {
      fetch(SESSION_CLEAR_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
      }).catch(() => {});
    }
  }

  function rotateChatSession() {
    clearBackendSessionCache();
    chatSessionId = newChatSessionId();
  }

  function renderUserMessage(text) {
    return escapeHtml(text).replace(/\r?\n/g, "<br>");
  }


  function getRowText(row) {
    return row?._translations?.[language] || Object.values(row?._translations || {})[0] || "";
  }

  function getMessageRows() {
    return Array.from(body.querySelectorAll(".message")).filter((row) => row._translations);
  }

  function latestUserRow() {
    return getMessageRows().filter((row) => row.classList.contains("user")).pop() || null;
  }

  function removeNodesAfter(row) {
    let node = row.nextSibling;
    while (node) {
      const next = node.nextSibling;
      node.remove();
      node = next;
    }
  }

  function syncChatHistoryBefore(row) {
    chatHistory.length = 0;
    for (const messageRow of getMessageRows()) {
      if (messageRow === row) {
        break;
      }
      const text = getRowText(messageRow);
      if (text) {
        rememberMessage(messageRow.classList.contains("user") ? "user" : "assistant", text);
      }
    }
  }

  function createEditButton(row) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "message-edit-button";
    button.setAttribute("aria-label", t("editMessage"));
    button.title = t("editMessage");
    button.textContent = "✎";
    button.addEventListener("click", () => startEditing(row));
    return button;
  }

  function updateEditableMessages() {
    const editableRow = !isSending && !editingRow ? latestUserRow() : null;
    body.querySelectorAll(".message-edit-button").forEach((button) => button.remove());
    if (editableRow && editableRow.isConnected) {
      editableRow.insertBefore(createEditButton(editableRow), editableRow.querySelector(".bubble"));
    }
  }

  function cancelEditing(row) {
    if (!row || editingRow !== row) {
      return;
    }
    editingRow = null;
    const text = getRowText(row);
    const bubble = row.querySelector(".bubble");
    bubble.innerHTML = renderUserMessage(text);
    row.classList.remove("editing");
    updateEditableMessages();
  }

  function startEditing(row) {
    if (!row || isSending) {
      return;
    }
    if (editingRow && editingRow !== row) {
      cancelEditing(editingRow);
    }

    editingRow = row;
    row.classList.add("editing");
    row.querySelector(".message-edit-button")?.remove();

    const text = getRowText(row);
    const bubble = row.querySelector(".bubble");
    bubble.innerHTML = "";

    const editor = document.createElement("form");
    editor.className = "message-edit-form";

    const textarea = document.createElement("textarea");
    textarea.className = "message-edit-input";
    textarea.rows = 3;
    textarea.value = text;
    textarea.setAttribute("aria-label", t("editMessage"));

    const actions = document.createElement("div");
    actions.className = "message-edit-actions";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "message-edit-cancel";
    cancel.textContent = t("cancelEdit");
    cancel.addEventListener("click", () => cancelEditing(row));

    const save = document.createElement("button");
    save.type = "submit";
    save.className = "message-edit-save";
    save.textContent = t("saveEdit");

    actions.append(cancel, save);
    editor.append(textarea, actions);
    editor.addEventListener("submit", (event) => {
      event.preventDefault();
      submitEditedMessage(row, textarea.value);
    });
    textarea.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        cancelEditing(row);
      }
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        editor.requestSubmit();
      }
    });

    bubble.append(editor);
    textarea.focus();
    textarea.setSelectionRange(text.length, text.length);
  }

  function bindPromptButtons(scope = document) {
    scope.querySelectorAll("[data-prompt-key]").forEach((button) => {
      button.addEventListener("click", () => sendMessage(t(button.dataset.promptKey)));
    });
  }

  function clearChat(event) {
    event?.preventDefault();
    clearLocalTranslationCache();
    rotateChatSession();
    requestSeq += 1;
    if (currentRequest) {
      currentRequest.abort();
      currentRequest = null;
    }
    currentTyping?.remove();
    currentTyping = null;
    chatHistory.length = 0;
    body.replaceChildren();
    body.insertAdjacentHTML("afterbegin", initialBodyHtml);
    bindPromptButtons(body);
    applyLanguage();
    body.scrollTop = 0;
    input.value = "";
    resizeInput();
    setComposerDisabled(false);
    editingRow = null;
    input.focus();
  }

  function addMessage(role, html, options = {}) {
    const row = document.createElement("div");
    row.className = `message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = `bubble${options.error ? " error" : ""}`;
    bubble.innerHTML = html;

    row.appendChild(bubble);
    if (typeof options.text === "string" && options.text) {
      row._translations = { [language]: options.text };
    }
    body.appendChild(row);
    updateEditableMessages();

    if (options.scroll === "start") {
      scrollToMessageStart(row);
    } else if (options.scroll !== false) {
      scrollToBottom();
    }

    return row;
  }

  function addTyping() {
    return addMessage(
      "agent",
      `<span class="typing" aria-label="${t("typingLabel")}"><span></span><span></span><span></span></span>`,
    );
  }

  function addSources(sources) {
    if (!Array.isArray(sources) || sources.length === 0) {
      return;
    }

    const visibleSources = sources
      .map((source) => String(source.url || "").trim())
      .filter(Boolean)
      .filter((url, index, urls) => urls.indexOf(url) === index)
      .slice(0, 5);

    if (visibleSources.length === 0) {
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "sources";
    wrapper.dataset.expanded = "false";
    wrapper.dataset.sourceCount = String(visibleSources.length);

    const toggle = document.createElement("button");
    toggle.className = "source-toggle";
    toggle.type = "button";
    toggle.textContent = `${t("sources")} ${visibleSources.length}`;
    toggle.addEventListener("click", () => {
      const expanded = wrapper.dataset.expanded === "true";
      wrapper.dataset.expanded = String(!expanded);
      toggle.textContent = expanded ? `${t("sources")} ${visibleSources.length}` : t("collapseSources");
    });

    const list = document.createElement("div");
    list.className = "source-list";

    visibleSources.forEach((url) => {
      const card = document.createElement("article");
      card.className = "source-card";

      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = url;
      link.title = url;

      card.append(link);
      list.appendChild(card);
    });

    wrapper.append(toggle, list);
    body.appendChild(wrapper);
  }

  function setComposerDisabled(disabled) {
    isSending = disabled;
    input.disabled = disabled;
    form.querySelector("button").disabled = disabled;
    languageButton.disabled = disabled;
    updateEditableMessages();
  }

  function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 108)}px`;
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function clearLocalTranslationCache() {
    document.querySelectorAll(".message").forEach((row) => {
      if (row._translations) {
        const currentText = row._translations[language] || Object.values(row._translations)[0] || "";
        row._translations = currentText ? { [language]: currentText } : {};
      }
      row._translationPromises = {};
      clearTranslating(row);
    });
  }

  function renderTranslatedRow(row, targetLanguage) {
    const text = row._translations?.[targetLanguage];
    if (!text) {
      return;
    }
    const bubble = row.querySelector(".bubble");
    bubble.innerHTML = row.classList.contains("user") ? renderUserMessage(text) : renderAnswer(text);
    clearTranslating(row);
  }

  function clearTranslating(row) {
    row.classList.remove("translating");
    row.removeAttribute("aria-busy");
    delete row.dataset.translatingLabel;
  }

  async function fetchTranslation(texts, targetLanguage, attempts = 2) {
    let lastError = null;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        const response = await fetch(TRANSLATE_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            texts,
            target_language: targetLanguage,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !Array.isArray(data.translations) || data.translations.length !== texts.length || !data.translations.every((item) => typeof item === "string")) {
          throw new Error(responseErrorMessage(data, t("serviceError")));
        }
        return data.translations;
      } catch (error) {
        lastError = error;
        if (attempt + 1 < attempts) {
          await sleep(250);
        }
      }
    }
    throw lastError || new Error(t("serviceError"));
  }

  async function ensureTranslations(rows, targetLanguage) {
    const missingRows = rows.filter((row) => !row._translations?.[targetLanguage]);
    const remoteRows = [];
    const remoteTexts = [];

    missingRows.forEach((row) => {
      const sourceText = Object.values(row._translations || {})[0];
      const localTranslation = localMessageTranslation(sourceText, targetLanguage);
      if (localTranslation) {
        row._translations[targetLanguage] = localTranslation;
        if (language === targetLanguage) {
          renderTranslatedRow(row, targetLanguage);
        }
        return;
      }
      if (sourceText) {
        remoteRows.push(row);
        remoteTexts.push(sourceText);
      }
    });

    if (!remoteRows.length) {
      return;
    }

    try {
      const translatedTexts = await fetchTranslation(remoteTexts, targetLanguage);
      remoteRows.forEach((row, index) => {
        row._translations[targetLanguage] = translatedTexts[index];
        if (language === targetLanguage) {
          renderTranslatedRow(row, targetLanguage);
        }
      });
    } catch (_) {
      const settled = await Promise.allSettled(remoteRows.map((row) => ensureTranslation(row, targetLanguage)));
      settled.forEach((result, index) => {
        const row = remoteRows[index];
        if (result.status === "fulfilled" && result.value && language === targetLanguage) {
          renderTranslatedRow(row, targetLanguage);
        }
      });
    }
  }

  async function ensureTranslation(row, targetLanguage) {
    row._translationPromises ||= {};
    if (row._translations?.[targetLanguage]) {
      return row._translations[targetLanguage];
    }
    if (row._translationPromises[targetLanguage]) {
      return row._translationPromises[targetLanguage];
    }

    const sourceText = Object.values(row._translations || {})[0];
    if (!sourceText) {
      return "";
    }

    const localTranslation = localMessageTranslation(sourceText, targetLanguage);
    if (localTranslation) {
      row._translations[targetLanguage] = localTranslation;
      if (language === targetLanguage) {
        renderTranslatedRow(row, targetLanguage);
      }
      return localTranslation;
    }

    const promise = (async () => {
      const translatedTexts = await fetchTranslation([sourceText], targetLanguage);
      row._translations[targetLanguage] = translatedTexts[0];
      if (language === targetLanguage) {
        renderTranslatedRow(row, targetLanguage);
      }
      return translatedTexts[0];
    })();

    row._translationPromises[targetLanguage] = promise;
    try {
      return await promise;
    } finally {
      delete row._translationPromises[targetLanguage];
    }
  }

  function syncChatHistory(rows, targetLanguage) {
    chatHistory.length = 0;
    rows.forEach((row) => {
      const text = row._translations?.[targetLanguage] || Object.values(row._translations || {})[0];
      if (text) {
        rememberMessage(row.classList.contains("user") ? "user" : "assistant", text);
      }
    });
  }

  async function requestAnswer(userRow, message, options = {}) {
    setComposerDisabled(true);

    const requestId = requestSeq + 1;
    requestSeq = requestId;
    const controller = new AbortController();
    currentRequest = controller;
    const typing = addTyping();
    currentTyping = typing;

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message, history: chatHistory.slice(-MAX_HISTORY_ITEMS), language, session_id: chatSessionId }),
        signal: controller.signal,
      });

      const data = await response.json().catch(() => ({}));

      if (requestId !== requestSeq) {
        return;
      }

      typing.remove();
      if (currentTyping === typing) {
        currentTyping = null;
      }

      if (!response.ok) {
        throw new Error(responseErrorMessage(data, t("serviceError")));
      }

      if (typeof data.answer !== "string" || !Array.isArray(data.sources)) {
        throw new Error(t("serviceError"));
      }
      const answerTranslations = data.answer_translations || {};
      if (
        typeof answerTranslations !== "object" ||
        Array.isArray(answerTranslations) ||
        !Object.values(answerTranslations).every((item) => typeof item === "string")
      ) {
        throw new Error(t("serviceError"));
      }
      const answer = data.answer || t("emptyAnswer");
      const answerRow = addMessage("agent", renderAnswer(answer), { scroll: "start", text: answer });
      Object.entries(answerTranslations).forEach(([translatedLanguage, translatedText]) => {
        if (translations[translatedLanguage] && translatedText) {
          answerRow._translations[translatedLanguage] = translatedText;
        }
      });
      addSources(data.sources);
      rememberMessage("user", message);
      rememberMessage("assistant", answer);

      const alternateLanguage = language === "zh-Hant" ? "en" : "zh-Hant";
      ensureTranslations([answerRow], alternateLanguage).catch(() => {});
      ensureTranslations([userRow], alternateLanguage).catch(() => {});
    } catch (error) {
      if (requestId !== requestSeq || error.name === "AbortError") {
        return;
      }
      typing.remove();
      if (currentTyping === typing) {
        currentTyping = null;
      }
      const errorText = error.message || t("connectionError");
      addMessage("agent", escapeHtml(errorText), {
        error: true,
        text: errorText,
      });
    } finally {
      if (currentRequest === controller) {
        currentRequest = null;
      }
      if (currentTyping === typing) {
        currentTyping = null;
      }
      if (requestId === requestSeq) {
        setComposerDisabled(false);
        if (options.focusInput !== false) {
          input.focus();
        }
      }
    }
  }

  async function sendMessage(message) {
    const trimmed = message.trim();

    if (!trimmed || isSending) {
      return;
    }

    if (editingRow) {
      cancelEditing(editingRow);
    }

    setOpen(true);
    const userRow = addMessage("user", renderUserMessage(trimmed), { text: trimmed });
    input.value = "";
    resizeInput();
    await requestAnswer(userRow, trimmed);
  }

  async function submitEditedMessage(row, message) {
    const trimmed = message.trim();
    if (!row || !trimmed || isSending) {
      return;
    }

    if (currentRequest) {
      currentRequest.abort();
      currentRequest = null;
    }
    currentTyping?.remove();
    currentTyping = null;
    requestSeq += 1;

    syncChatHistoryBefore(row);
    removeNodesAfter(row);
    row._translations = { [language]: trimmed };
    row._translationPromises = {};
    editingRow = null;
    row.classList.remove("editing");
    row.querySelector(".bubble").innerHTML = renderUserMessage(trimmed);
    updateEditableMessages();
    scrollToMessageStart(row);

    await requestAnswer(row, trimmed);
  }

  openButton.addEventListener("click", () => setOpen(true));
  closeButton.addEventListener("click", () => setOpen(false));
  if (clearButton) {
    clearButton.addEventListener("click", clearChat);
  }

  async function switchLanguage() {
    if (isSending || languageButton.disabled) {
      return;
    }
    if (editingRow) {
      cancelEditing(editingRow);
    }

    const switchId = Date.now();
    languageButton.dataset.switchId = String(switchId);
    const targetLanguage = language === "zh-Hant" ? "en" : "zh-Hant";
    const rows = Array.from(body.querySelectorAll(".message")).filter((row) => row._translations);

    language = targetLanguage;
    localStorage.setItem("nthu-chat-language", language);
    applyLanguage();

    languageButton.disabled = true;
    rows.forEach((row) => {
      if (row._translations[targetLanguage]) {
        renderTranslatedRow(row, targetLanguage);
      } else {
        row.classList.add("translating");
        row.setAttribute("aria-busy", "true");
        row.dataset.translatingLabel = t("translating");
      }
    });

    try {
      await ensureTranslations(rows, targetLanguage);
      const stillMissing = rows.filter((row) => !row._translations?.[targetLanguage]);
      if (stillMissing.length) {
        await ensureTranslations(stillMissing, targetLanguage);
      }

      if (languageButton.dataset.switchId !== String(switchId) || language !== targetLanguage) {
        return;
      }

      rows.forEach((row) => {
        if (row._translations?.[targetLanguage]) {
          renderTranslatedRow(row, targetLanguage);
        } else {
          clearTranslating(row);
        }
      });
      syncChatHistory(rows, targetLanguage);
      applyLanguage();
    } finally {
      if (languageButton.dataset.switchId === String(switchId)) {
        languageButton.disabled = false;
      }
      input.focus();
    }
  }

  languageButton.addEventListener("click", switchLanguage);
  window.addEventListener("pagehide", () => {
    clearLocalTranslationCache();
    clearBackendSessionCache();
  });
  window.addEventListener("beforeunload", () => {
    clearLocalTranslationCache();
    clearBackendSessionCache();
  });

  applyLanguage();
  bindPromptButtons(document);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });

  input.addEventListener("input", resizeInput);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && widget.dataset.open === "true") {
      setOpen(false);
    }
  });
})();
