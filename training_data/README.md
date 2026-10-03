# 清大網路 AI 額外訓練資料

這個目錄放的是可人工調整的文字訓練資料，用來改善客服助理的回答方式、範圍判斷與資訊不足時的追問品質。

檔案用途：

- `01_specific_qa.jsonl`：常見清大網路問題的具體回答範例。
- `02_clarifying_questions.jsonl`：問題資訊不足時，應該追問哪些欄位。
- `03_out_of_scope.jsonl`：非清大網路範圍問題的拒答方式。
- `04_rag_grounded_answers.jsonl`：示範根據 RAG 摘要資料回答，不自行編造。
- `05_failure_rewrites.jsonl`：把制式或不理想回答改寫成具體回答。
- `06_user_feedback_expected_answers.jsonl`：使用者在 UI 測試後提供的「問題 / AI 目前回答 / 期望回答」修正版範例。

注意：這些資料主要訓練回答行為與格式，不應取代 RAG 中的官方事實資料。正式訓練前，請依清大網路系統組最新文件修正內容、連結、帳號格式與聯絡方式。


本次已依據 FAQ 擴充資料來源：

- https://net.nthu.edu.tw/netsys/faq#wireless
- https://net.nthu.edu.tw/netsys/dormnet#常見問題

擴充重點包含校園無線網路申請、使用範圍、認證方式、密碼變更、漫遊、連線失敗排查，以及宿舍網路申請、校內 IP 限制、TCP/IP 設定、無法辨識網路、宿網突然不通、狀態查詢與分享器相關問題。


最新補充：地點型 Wi-Fi 範圍問題（例如人社院、小吃部、風雲樓、餐廳、院系館舍是否有網路）應主要依據 https://net.nthu.edu.tw/netsys/faq:wlan_range；除非明確提到宿舍、宿網、宿舍網路孔或宿舍各齋住宿網路，否則不要提宿網。
地點型問題若同時包含校內 FAQ 有列出的地點與校外店家，需逐一判斷；例如「小吃部跟紅吱吱牛排有提供網路嗎？」應回答小吃部有，紅吱吱牛排等校外餐廳不屬於清大校園無線網路涵蓋範圍。
多輪對話需保留脈絡；若上一題是「資電館有網路嗎？」這類校園地點無線網路問題，下一題「我要怎麼連啊」應直接回答校園無線網路連線方式，不要重新要求使用者在宿網/無線網路間選擇。
梅園覆蓋判斷以無線網路覆蓋圖為準；梅園不在目前可確認的紅色覆蓋範圍內，因此回答沒有清大校園無線網路覆蓋。


## English answer training data

`07_english_expected_answers.jsonl` contains English-only expected answers for DormNet, campus Wi-Fi, and email. English requests use these examples independently from the Traditional Chinese examples. Official facts should primarily come from:

- https://net.nthu.edu.tw/netsys/en:faq#dormnet
- https://net.nthu.edu.tw/netsys/en:faq#wireless_network
- https://net.nthu.edu.tw/netsys/en:faq#mail

The linked English detail pages are crawled and indexed as priority sources. English retrieval boosts `/netsys/en:` pages and lowers the rank of Chinese pages.

## Multilingual consistency policy

When a fact, instruction, URL, account format, policy, or expected answer is found to be incorrect in any language, review and correct the corresponding answer data in every supported language at the same time. Do not apply factual corrections to only the language in which the issue was reported.

新增或修正任何語言版本的資料時，若確認內容、操作步驟、網址、帳號格式、政策或預期回答有誤，必須同步檢查並修正所有支援語言的對應回答資料，不可只修正回報問題的單一語言版本。
