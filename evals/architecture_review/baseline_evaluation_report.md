# Architecture Review Evaluation — baseline

Generated: 2026-08-29T00:47:07+08:00

## Dataset and outcome

- Conversations: 275
- Turns: 337
- Conversation pass rate: 0.3018
- Turn pass rate: 0.3798

## Required metrics

| Metric | Passed | Total | Rate |
|---|---:|---:|---:|
| single_turn_accuracy | 70 | 220 | 0.3182 |
| zh_single_turn_accuracy | 54 | 110 | 0.4909 |
| en_single_turn_accuracy | 16 | 110 | 0.1455 |
| multi_turn_success_rate | 58 | 117 | 0.4957 |
| topic_switch_accuracy | 7 | 8 | 0.875 |
| intent_switch_accuracy | 3 | 8 | 0.375 |
| backward_reference_accuracy | 4 | 5 | 0.8 |
| retrieval_isolation_correctness | 211 | 216 | 0.9769 |
| bilingual_consistency | 4 | 20 | 0.2 |

## Failure distribution

| Primary failure | Count |
|---|---:|
| INTENT_ERROR | 104 |
| TOPIC_ERROR | 59 |
| REFERENCE_ERROR | 27 |
| GENERATION_ERROR | 13 |
| ENTITY_ERROR | 3 |
| REFUSAL_ERROR | 3 |

## Representative failures

### zh_single_005 / turn 1 — INTENT_ERROR

- User: 欸學校 WiFi 帳密要怎麼辦啊
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: 清大無線網路帳號與密碼不是校務資訊系統那組，而是另外申請的「校園無線區域網路帳號」。

**帳號與密碼怎麼來**
1. 先到校務資訊系統中的「計通中心相關服務」裡的「網路系統組線上服務」。
2. 選擇「無線區域網路帳號」進行申請。
3. 申請時會設定無線網路密碼，之後連 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 時使用這組帳密。

若是在清大校內使用 `nthupeap` 或 `eduroam`，帳號格式通常為 `s學號`；若是在外校使用 `eduroam` 漫遊，帳號格式為 `s學號@wlan.nthu.edu.tw`。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/faq:wlan_auth

### zh_single_007 / turn 1 — INTENT_ERROR

- User: eduroam 的清大帳號怎麼開
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: 在外校使用 `eduroam` 漫遊時，帳號請輸入：

`s學號@wlan.nthu.edu.tw`

密碼是你申請清大校園無線區域網路帳號時設定的密碼，不一定是校務資訊系統密碼。

如果是在清大校內使用 `eduroam` 或 `nthupeap`，帳號通常只要輸入 `s學號`。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/faq:wlan_auth

### zh_single_008 / turn 1 — TOPIC_ERROR

- User: wify 帳號要去哪申請
- Actual state: topic=account, intent=application, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: TOPIC_ERROR
- Answer: 清大無線網路帳號與密碼不是校務資訊系統那組，而是另外申請的「校園無線區域網路帳號」。

**帳號與密碼怎麼來**
1. 先到校務資訊系統中的「計通中心相關服務」裡的「網路系統組線上服務」。
2. 選擇「無線區域網路帳號」進行申請。
3. 申請時會設定無線網路密碼，之後連 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 時使用這組帳密。

若是在清大校內使用 `nthupeap` 或 `eduroam`，帳號格式通常為 `s學號`；若是在外校使用 `eduroam` 漫遊，帳號格式為 `s學號@wlan.nthu.edu.tw`。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/faq:wlan_auth

### zh_single_011 / turn 1 — INTENT_ERROR

- User: nthu-cc 連上但不能上網
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: `nthu-cc` 是清大校內無線網路的 Web-based 認證 Wi-Fi。使用方式如下：

1. 在校內 Wi-Fi 清單中選擇 `nthu-cc`。
2. 連上後打開瀏覽器，系統通常會自動跳出登入頁面。
3. 在登入頁面輸入無線網路帳號與密碼後即可上網。
4. 如果登入頁面沒有自動跳出，請手動開啟 Chrome、Firefox、Edge 或 Safari，連到任一網頁，通常就會導出認證頁面。
5. 若仍無法使用，可先關閉 Wi-Fi 後重新開啟，再重新連線一次。

**尋求幫助**
若仍無法登入或上網，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、裝置系統、連線的 SSID、錯誤訊息，並附上 Wi-Fi 設定或登入畫面截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/faq:wlan_useless

### zh_single_017 / turn 1 — INTENT_ERROR

- User: 無線網路取得不到 IP
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR
- Answer: 無線網路取得不到 IP，通常是裝置的 IP 設定沒有設為自動取得。

**檢查 IP 設定**

1. **確認 IP 為自動取得：** 到裝置的網路設定中，將無線網路的 IPv4 設定改為「自動取得」（也就是 DHCP），不要使用手動 IP。
2. **重連 Wi-Fi：** 先忘記該 Wi-Fi 連線，再重新連線，讓裝置重新向伺服器請求 IP。
3. **重開裝置 Wi-Fi：** 若重連後仍沒有 IP，關閉 Wi-Fi 再開啟，或重開裝置再試一次。

**尋求幫助**

若以上步驟完成後仍無法取得 IP，請將以下資訊寄到 wlan@cc.nthu.edu.tw：目前所在位置與樓層、連線的 SSID（nthu-cc、TANetRoaming、nthupeap 或 eduroam）、裝置作業系統、錯誤訊息或截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_useless

### zh_single_018 / turn 1 — INTENT_ERROR

- User: 欸為啥 nthu-cc 登入頁死都不跳
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: `nthu-cc` 是清大校內無線網路的 Web-based 認證 Wi-Fi。使用方式如下：

1. 在校內 Wi-Fi 清單中選擇 `nthu-cc`。
2. 連上後打開瀏覽器，系統通常會自動跳出登入頁面。
3. 在登入頁面輸入無線網路帳號與密碼後即可上網。
4. 如果登入頁面沒有自動跳出，請手動開啟 Chrome、Firefox、Edge 或 Safari，連到任一網頁，通常就會導出認證頁面。
5. 若仍無法使用，可先關閉 Wi-Fi 後重新開啟，再重新連線一次。

**尋求幫助**
若仍無法登入或上網，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、裝置系統、連線的 SSID、錯誤訊息，並附上 Wi-Fi 設定或登入畫面截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/faq:wlan_useless

### zh_single_019 / turn 1 — REFERENCE_ERROR

- User: wifi 剛剛能用現在掛惹
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=unresolved []
- Route: reference_clarification
- Failures: INTENT_ERROR, REFERENCE_ERROR
- Answer: 我找不到你提到的前一題或第一個問題。請把那個問題再貼一次，或補充服務名稱（例如宿網、校園 Wi-Fi、VPN 或信箱），我才能接著回答。

### zh_single_021 / turn 1 — ENTITY_ERROR

- User: 人社有網路嗎
- Actual state: topic=campus_wifi, intent=lookup, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: ENTITY_ERROR
- Answer: 有。「人社館」可使用的校園無線網路為 `nthupeap`。

實際連線時仍應以所在樓層現場可搜尋到的 SSID 與訊號為準。

### zh_single_024 / turn 1 — INTENT_ERROR

- User: 綜四有沒有無線
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR
- Answer: 目前資料中沒有第四綜合大樓的無線網路覆蓋資訊，無法確認綜四是否有清大校園無線網路覆蓋。

你可以查看校園無線網路覆蓋圖，紅色範圍代表有覆蓋：
https://net.nthu.edu.tw/netsys/_media/wireless:wlan-cover-color.jpg?cache=

若覆蓋圖上仍不確定，可寫信至 wlan@cc.nthu.edu.tw 詢問。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy

### zh_single_026 / turn 1 — ENTITY_ERROR

- User: 欸所以水木勒，有 wifi 嗎
- Actual state: topic=campus_wifi, intent=lookup, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: ENTITY_ERROR
- Answer: **水木生活中心**
水木生活中心列在公共區無線網路範圍中，可先嘗試使用校園無線網路。

若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy

### zh_single_028 / turn 1 — INTENT_ERROR

- User: 風雲樓有沒有學校 Wi-Fi
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: **風雲樓**
風雲樓列在公共區無線網路範圍中，可先嘗試使用校園無線網路。

若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy

### zh_single_029 / turn 1 — INTENT_ERROR

- User: 小吃部 wifi 收得到嗎
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: **小吃部**
小吃部與小吃部戶外廣場列在公共區無線網路範圍中，可先嘗試使用校園無線網路。

若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy

### zh_single_031 / turn 1 — INTENT_ERROR

- User: 物理館能連校園網路嗎
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR
- Answer: 目前資料中沒有明確列出物理館的無線網路覆蓋資訊，無法確認該館是否有清大校園無線網路覆蓋。建議您到現場開啟裝置的 Wi-Fi 列表，看是否有 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 等訊號，即可判斷該位置是否有覆蓋。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range

### zh_single_035 / turn 1 — INTENT_ERROR

- User: 成功湖附近有校園 wifi 嗎
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR
- Answer: 目前資料中未列出成功湖有校園無線網路覆蓋，無法確認該處是否可用。建議查看無線網路覆蓋圖（紅色範圍代表有覆蓋）來確認成功湖周邊是否有訊號。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/_media/wireless:wlan-cover-color.jpg?cache=

### zh_single_036 / turn 1 — INTENT_ERROR

- User: 操場有無線嗎
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR
- Answer: 目前可確認的校園無線網路涵蓋範圍資料中，沒有明確列出「操場」這個地點，因此無法確認操場有清大校園無線網路覆蓋。

比較接近的是「體育館戶外廣場（梅園入口處區域）」有覆蓋，如果你站在操場靠近體育館廣場那一側，有可能收到訊號，但無法保證整片操場都有。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range

### zh_single_038 / turn 1 — INTENT_ERROR

- User: 請問綜合四館的 Wi-Fi 覆蓋狀況
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR
- Answer: 目前可確認的無線網路服務範圍資料中，沒有列出「綜合四館」（第四綜合大樓）的覆蓋資訊，因此無法確認該地點是否有清大校園無線網路。

資料中列出的綜合大樓相關覆蓋僅有「第三綜合大樓 8F」（SSID：nthupeap、eduroam），與綜合四館不同。

**尋求幫助**
若您需要確認綜合四館是否有無線網路覆蓋，可來信 wlan@cc.nthu.edu.tw 詢問。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range

### zh_single_039 / turn 1 — INTENT_ERROR

- User: 校園 Wi-Fi 帳密是什麼
- Actual state: topic=campus_wifi, intent=general, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: 清大無線網路帳號與密碼不是校務資訊系統那組，而是另外申請的「校園無線區域網路帳號」。

**帳號與密碼怎麼來**
1. 先到校務資訊系統中的「計通中心相關服務」裡的「網路系統組線上服務」。
2. 選擇「無線區域網路帳號」進行申請。
3. 申請時會設定無線網路密碼，之後連 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 時使用這組帳密。

若是在清大校內使用 `nthupeap` 或 `eduroam`，帳號格式通常為 `s學號`；若是在外校使用 `eduroam` 漫遊，帳號格式為 `s學號@wlan.nthu.edu.tw`。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/faq:wlan_auth

### zh_single_040 / turn 1 — REFUSAL_ERROR

- User: nthupeap 密碼填哪組
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: REFUSAL_ERROR
- Answer: 目前無法根據可用的清大網路資料產生可靠回答。請補充服務類型與地點，例如宿網、校園 Wi-Fi、VPN 或信箱。

### zh_single_043 / turn 1 — TOPIC_ERROR

- User: 學校無線跟校務系統是同一組密碼嗎
- Actual state: topic=account, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: TOPIC_ERROR
- Answer: 清大無線網路帳號與密碼不是校務資訊系統那組，而是另外申請的「校園無線區域網路帳號」。

**帳號與密碼怎麼來**
1. 先到校務資訊系統中的「計通中心相關服務」裡的「網路系統組線上服務」。
2. 選擇「無線區域網路帳號」進行申請。
3. 申請時會設定無線網路密碼，之後連 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 時使用這組帳密。

若是在清大校內使用 `nthupeap` 或 `eduroam`，帳號格式通常為 `s學號`；若是在外校使用 `eduroam` 漫遊，帳號格式為 `s學號@wlan.nthu.edu.tw`。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/faq:wlan_auth

### zh_single_045 / turn 1 — TOPIC_ERROR

- User: 無線帳密忘了要去哪改
- Actual state: topic=unknown, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: TOPIC_ERROR
- Answer: 清大無線網路帳號與密碼不是校務資訊系統那組，而是另外申請的「校園無線區域網路帳號」。

**帳號與密碼怎麼來**
1. 先到校務資訊系統中的「計通中心相關服務」裡的「網路系統組線上服務」。
2. 選擇「無線區域網路帳號」進行申請。
3. 申請時會設定無線網路密碼，之後連 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 時使用這組帳密。

若是在清大校內使用 `nthupeap` 或 `eduroam`，帳號格式通常為 `s學號`；若是在外校使用 `eduroam` 漫遊，帳號格式為 `s學號@wlan.nthu.edu.tw`。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/faq:wlan_auth
