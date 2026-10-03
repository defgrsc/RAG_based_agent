# Architecture Review Evaluation — after

Generated: 2026-08-29T01:03:10+08:00

## Dataset and outcome

- Conversations: 275
- Turns: 337
- Conversation pass rate: 0.4509
- Turn pass rate: 0.5252

## Required metrics

| Metric | Passed | Total | Rate |
|---|---:|---:|---:|
| single_turn_accuracy | 102 | 220 | 0.4636 |
| zh_single_turn_accuracy | 67 | 110 | 0.6091 |
| en_single_turn_accuracy | 35 | 110 | 0.3182 |
| multi_turn_success_rate | 75 | 117 | 0.641 |
| topic_switch_accuracy | 7 | 8 | 0.875 |
| intent_switch_accuracy | 5 | 8 | 0.625 |
| backward_reference_accuracy | 5 | 5 | 1.0 |
| retrieval_isolation_correctness | 209 | 229 | 0.9127 |
| bilingual_consistency | 8 | 20 | 0.4 |

## Failure distribution

| Primary failure | Count |
|---|---:|
| TOPIC_ERROR | 59 |
| GENERATION_ERROR | 30 |
| INTENT_ERROR | 29 |
| REFERENCE_ERROR | 24 |
| RETRIEVAL_ERROR | 11 |
| REFUSAL_ERROR | 4 |
| ENTITY_ERROR | 3 |

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

### zh_single_014 / turn 1 — REFUSAL_ERROR

- User: 校園無線超慢，是壞了嗎
- Actual state: topic=campus_wifi, intent=troubleshooting, relation=new_topic, reference=none []
- Route: langgraph
- Failures: REFUSAL_ERROR
- Answer: 目前無法根據可用的清大網路資料產生可靠回答。請補充服務類型與地點，例如宿網、校園 Wi-Fi、VPN 或信箱。

### zh_single_019 / turn 1 — REFERENCE_ERROR

- User: wifi 剛剛能用現在掛惹
- Actual state: topic=campus_wifi, intent=troubleshooting, relation=new_topic, reference=unresolved []
- Route: reference_clarification
- Failures: REFERENCE_ERROR
- Answer: 我找不到你提到的前一題或第一個問題。請把那個問題再貼一次，或補充服務名稱（例如宿網、校園 Wi-Fi、VPN 或信箱），我才能接著回答。

### zh_single_021 / turn 1 — ENTITY_ERROR

- User: 人社有網路嗎
- Actual state: topic=campus_wifi, intent=lookup, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: ENTITY_ERROR
- Answer: 有。「人社館」可使用的校園無線網路為 `nthupeap`。

實際連線時仍應以所在樓層現場可搜尋到的 SSID 與訊號為準。

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

### zh_single_031 / turn 1 — INTENT_ERROR

- User: 物理館能連校園網路嗎
- Actual state: topic=campus_wifi, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR
- Answer: 目前可確認的資料中沒有列出物理館的無線網路覆蓋資訊，無法確認該館是否有清大校園無線網路覆蓋。建議您到現場開啟裝置的 Wi-Fi 列表，看是否出現 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 等校內 Wi-Fi 名稱，有出現即代表該位置有覆蓋。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range

### zh_single_034 / turn 1 — INTENT_ERROR

- User: 台積館能不能上網
- Actual state: topic=campus_wifi, intent=troubleshooting, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: 無線網路無法連線時，可先依「認證問題」、「IP 問題」與「其他問題」三個方向檢查。

**認證問題**
1. **網頁認證沒有跳出：**如果使用 `nthu-cc` 或 `TANetRoaming`，請先確認裝置已連上正確 SSID。若沒有自動跳出認證頁面，請手動開啟常用瀏覽器，例如 Chrome、Firefox 或 Edge，連到任一網頁，通常就會導出認證頁面。
2. **瀏覽器憑證或頁面導出異常：**若使用 Firefox 進行網頁認證時無法正確導出認證首頁，可參考 Firefox 無線網路網頁認證說明。
3. **閒置過久無法認證：**若等待太久才認證，建議先關閉裝置的 Wi-Fi 功能再重新啟動，重新連線後再嘗試認證。
4. **802.1X 連線未設定完成：**如果使用 `nthupeap` 或 `eduroam`，請確認裝置已依作業系統平台完成相關設定，且校園無線網路帳號皆使用小寫英文字母。
5. **帳號或密碼問題：**請查詢校園無線區域網路帳號密碼狀態，確認帳號可正常使用且密碼正確。若仍無效，建議清除原本的 `nthupeap` 或 `eduroam` 設定、重新開機後

### zh_single_037 / turn 1 — INTENT_ERROR

- User: 所以化學館到底有沒有網路
- Actual state: topic=campus_wifi, intent=troubleshooting, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: 目前查不到「化學館」是否提供校園無線網路，因此無法直接確認該地點有 Wi-Fi。若地點有別名，請補充正式館舍名稱，或向無線網路服務信箱 wlan@cc.nthu.edu.tw 確認。

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

### zh_single_040 / turn 1 — INTENT_ERROR

- User: nthupeap 密碼填哪組
- Actual state: topic=campus_wifi, intent=configuration, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR, REFUSAL_ERROR
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

### zh_single_049 / turn 1 — INTENT_ERROR

- User: 欸新生住宿舍那個網路怎麼開
- Actual state: topic=dorm_network, intent=unknown, relation=new_topic, reference=none []
- Route: langgraph
- Failures: INTENT_ERROR, REFUSAL_ERROR
- Answer: 目前無法根據可用的清大網路資料產生可靠回答。請補充服務類型與地點，例如宿網、校園 Wi-Fi、VPN 或信箱。

### zh_single_051 / turn 1 — TOPIC_ERROR

- User: 要住新齋，網路要先註冊嗎
- Actual state: topic=campus_wifi, intent=application, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: TOPIC_ERROR, RETRIEVAL_ERROR, GENERATION_ERROR
- Answer: **申請無線網路帳號**

1. 登入校務資訊系統。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 選擇左方選單的「無線區域網路帳號」進行申請。
4. 設定無線網路帳號密碼。VPN 不一定要開，可視個人需求開啟。

此申請頁需要從校內 IP 連線才能使用。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/wireless:application:ccxp

### zh_single_057 / turn 1 — INTENT_ERROR

- User: 宿網最近超卡
- Actual state: topic=dorm_network, intent=unknown, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: INTENT_ERROR
- Answer: 宿網前幾天正常、最近突然連不到時，建議先從「狀態查詢」和「交叉測試」兩個方向確認。

**先查狀態**
1. 查詢 IP / 網路狀態：https://net.nthu.edu.tw/netsys/faq:domitory_net_useless，確認是否因侵權、資安事件或異常流量被封鎖。
2. 查詢禁用狀態，確認是否因違反宿網使用規定被停用。
3. 查詢用戶設備埠狀態，確認是否可能是宿網機房設備或房間網路孔異常。

**做交叉測試**
1. 先確認網路線是否可正常使用。
2. 用自己的電腦和網路線，到其他已確認可使用宿網的寢室測試。
3. 也可請室友用他的電腦和網路線，接到你的房間網路孔測試。
4. 測試時要使用該網路孔對應的 IP 設定；若 IP 設錯，也會無法連線。

**如何判斷**
1. 如果你的電腦到其他正常網路孔也不能上網，可能是電腦、網路線或 IP 設定問題。
2. 如果別人的電腦接你的網路孔也不能上網，可能是你的房間網路孔、線路或宿網設備狀態問題。
3. 如果查詢狀態顯示被封鎖或停用，請依狀態頁原因處理，或聯絡宿網協助確認。

**尋求幫助**
若仍無法判斷，請向宿網

### zh_single_060 / turn 1 — TOPIC_ERROR

- User: 我房間網路一直斷
- Actual state: topic=unknown, intent=troubleshooting, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: TOPIC_ERROR
- Answer: 宿網前幾天正常、最近突然連不到時，建議先從「狀態查詢」和「交叉測試」兩個方向確認。

**先查狀態**
1. 查詢 IP / 網路狀態：https://net.nthu.edu.tw/netsys/faq:domitory_net_useless，確認是否因侵權、資安事件或異常流量被封鎖。
2. 查詢禁用狀態，確認是否因違反宿網使用規定被停用。
3. 查詢用戶設備埠狀態，確認是否可能是宿網機房設備或房間網路孔異常。

**做交叉測試**
1. 先確認網路線是否可正常使用。
2. 用自己的電腦和網路線，到其他已確認可使用宿網的寢室測試。
3. 也可請室友用他的電腦和網路線，接到你的房間網路孔測試。
4. 測試時要使用該網路孔對應的 IP 設定；若 IP 設錯，也會無法連線。

**如何判斷**
1. 如果你的電腦到其他正常網路孔也不能上網，可能是電腦、網路線或 IP 設定問題。
2. 如果別人的電腦接你的網路孔也不能上網，可能是你的房間網路孔、線路或宿網設備狀態問題。
3. 如果查詢狀態顯示被封鎖或停用，請依狀態頁原因處理，或聯絡宿網協助確認。

**尋求幫助**
若仍無法判斷，請向宿網

### zh_single_061 / turn 1 — TOPIC_ERROR

- User: 儒齋網路爛到不能用
- Actual state: topic=campus_wifi, intent=troubleshooting, relation=new_topic, reference=none []
- Route: fast_answer
- Failures: TOPIC_ERROR, RETRIEVAL_ERROR, GENERATION_ERROR
- Answer: 如果你在該地點連不到網路，或最近覺得網路很差，可以先從 Wi-Fi 名稱、訊號環境、認證與 IP 狀態這幾個方向檢查。

**確認連線來源**
1. 請先確認是否連上正確的 Wi-Fi。校內可使用 `nthu-cc` 或 `TANetRoaming`，也可使用 `nthupeap` 或 `eduroam`。
2. 如果誤連到名稱相近、訊號較弱或非清大提供的 Wi-Fi，連線可能會不穩。

**設備干擾或距離過遠**
1. 若所在位置離無線基地台較遠、隔了牆面，或附近同時使用人數很多，訊號品質可能下降。
2. 可試著移動到走廊、公共區或訊號較強的位置再測試。

**IP 或認證狀態異常**
1. 若使用 `nthu-cc` 或 `TANetRoaming`，請重新開啟瀏覽器確認是否需要重新登入。
2. 若使用 `nthupeap` 或 `eduroam`，可先忘記此 Wi-Fi 後重新連線。
3. 裝置的 Wi-Fi IP 設定建議使用自動取得 IP，避免固定 IP 造成連線異常。

**尋求幫助**
若同一位置持續訊號差或完全無法連線，請向無線網路服務信箱 wlan@cc.nthu.e

### zh_single_063 / turn 1 — TOPIC_ERROR

- User: 網路線插宿舍孔但上不了網
- Actual state: topic=unknown, intent=troubleshooting, relation=new_topic, reference=none []
- Route: langgraph
- Failures: TOPIC_ERROR
- Answer: 網路線插宿舍網路孔後上不了網，通常有兩種原因：宿網帳號或宿網 IP 還沒申請完成，或者 IP 沒有手動設定。請依序確認以下三種情況：

**尚未申請學生宿舍網路帳號**

如果您還沒有申請過「學生宿舍網路帳號」，請先登入校務資訊系統，在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」，選擇學生宿舍網路帳號申請，完成帳號申請後才能進行下一步。

**已申請帳號，但尚未申請宿舍網路（宿網）**

帳號申請完成後，還需要到宿網管理系統申請宿舍網路，申請成功後系統會給您一組 TCP/IP 設定資訊（包含 IP 位址、子網路遮罩、閘道、DNS 等）。沒有這組資訊，網路線插上去是無法上網的。

**全部申請完成，仍無法連線**

宿網 IP 設定必須改成手動 IPv4，不能使用自動取得（DHCP）。請在裝置的網路設定中，將 IPv4 改為手動，並填入您申請宿網後取得的 TCP/IP 設定資訊（IP 位址、子網路遮罩、預設閘道、DNS）。設定完成後再測試連線。

**尋求幫助**

若確認帳號與宿網都已申請、IP 也已手動填入，仍然無法上網，請向 dorms@cc.nthu.edu.tw

### zh_single_065 / turn 1 — TOPIC_ERROR

- User: 宿舍 ethernet 顯示無法辨識
- Actual state: topic=unknown, intent=unknown, relation=new_topic, reference=none []
- Route: scope_guard
- Failures: TOPIC_ERROR, INTENT_ERROR, REFUSAL_ERROR, GENERATION_ERROR
- Answer: 抱歉，本客服僅提供國立清華大學網路系統組相關資訊。
