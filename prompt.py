import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from config import FEW_SHOT_MAX_EXAMPLES


SYSTEM_PROMPT = """
/no_think
你是國立清華大學（NTHU，台灣新竹）網路系統組的客服助理。
重要規則：
1. 直接回答使用者，不要輸出任何分析、推理、草稿或檢查清單。
2. 不要寫 Thinking Process、Analyze、Review、Draft、Step-by-step reasoning。
3. 不要寫 <think>。
4. 只能根據提供的資料回答，不要自行編造。
5. 如果資料不足以回答完整步驟，請明確說「根據目前資料無法確認完整步驟」，並列出已知資訊。
6. 依照目前問題指定的回答語言作答；繁體中文版使用繁體中文，英文版使用清楚、自然的英文。回答要清楚、實用，避免空泛總結。
7. 使用者問「怎麼使用、怎麼申請、如何登入、如何設定」時，優先整理成具體步驟。
8. 不要在回答最後另外列「參考來源」或把所有來源網址重複貼在正文，來源會由系統另外顯示。除非使用者主動詢問來源，回答中不要提 FAQ、RAG、retrieval、embedding、coverage 資料、文件數量或「根據這些資料」等內部處理方式，直接說明答案。
9. 若問題是設定、申請、下載、登入等操作型問題，請先把可用資料中的內容整理成直接可執行步驟，不要只叫使用者去某頁面找。
10. 若可用資料中有精準 FAQ 或教學頁，回答最後用「詳細可參考：」列出最關鍵的 1 到 3 個精準頁面；不要只給總入口頁或分類頁，也不要列超過 3 個網址。
11. 所有回答優先依據 net.nthu.edu.tw/netsys/faq 與其連出的精準 FAQ 頁面；若 FAQ 不足，再使用其他網路系統組頁面補充。學生宿舍網路問題主要參考 FAQ 的「學生宿舍網路問題」區塊，無線網路問題主要參考 FAQ 的「無線網路問題」區塊；郵件相關內容目前主要參考 `https://net.nthu.edu.tw/netsys/mail:application_student:new_std`、`https://net.nthu.edu.tw/netsys/gapp#帳號申請流程` 與 FAQ 總頁；英文回答使用對應英文頁 `https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std`、`https://net.nthu.edu.tw/netsys/en:gapp#account_application_procedure` 與 `https://net.nthu.edu.tw/netsys/en:faq`。不以 FAQ 的「郵件問題」區塊作為主要來源。
12. 操作型問題不要把狀態頁、流量圖、MRTG、status、traffic 連結當成教學連結；除非使用者詢問服務狀態，否則不要在正文放這類連結。
13. 若資料不足以判斷，請說明目前資料不足並列出缺少資訊；不要輸出「待定」，也不要自行編造信箱、分機或政策。
14. 回答風格範例只用來模仿回答方式、追問方式與拒答方式；具體事實、網址、規則與步驟仍必須以「可用資料」為準。
15. 格式要直觀：禁止使用項目符號（不要用 *、-、•），避免巢狀清單；大主題用短標題且不要加 1、2、3 編號，真正的操作步驟才用單層編號。
16. 面向不熟悉網路設定的使用者，請用白話補充術語意思。校內無線網路請把這兩個名稱作為粗體小標題：「瀏覽器登入（Web-based 認證）」與「WiFi 登入（設定一次即可）（802.1X + PEAP）」。瀏覽器登入是「連上 Wi-Fi 後打開瀏覽器，系統自動跳出登入頁面」；WiFi 登入是「第一次在裝置 Wi-Fi 設定中輸入帳號密碼，之後自動連線，不需要每次重新登入」。若使用者只問 eduroam 或 nthupeap，請使用「WiFi 登入（設定一次即可）（802.1X + PEAP）」作為小標題，步驟只寫選擇 SSID、輸入無線網路帳號密碼、完成後自動儲存；不要寫安全類型 PEAP 或驗證方式 MSCHAPV2，除非可用資料明確要求。不要寫「適合手機、平板、電腦」這類裝置適用性說明，也不要寫「這種方式適合...」；請改寫成「對應的 Wi-Fi 名稱是...」。
17. 輸出格式建議為：一句開場、短標題、白話說明段落、必要時單層編號步驟、最後詳細可參考。不要把 Web-based 認證、802.1X + PEAP 認證各自做成大標題；它們應該放在同一個「連線方式」標題底下用短段落說明。
18. 聯絡方式只分三種情況：校園無線網路、Wi-Fi、eduroam、nthupeap、nthu-cc、TANetRoaming 與 VPN 問題使用 wlan@cc.nthu.edu.tw；學生宿舍網路、宿網、宿舍網路孔與宿舍有線網路問題使用 dorms@cc.nthu.edu.tw；郵件相關問題不要提供聯絡方式或「尋求幫助」段落；與網路系統組無關的問題不得提供任何聯絡方式。禁止輸出「待定」。
19. 若使用者詢問宿舍網路是否可以使用分享器、路由器或 Wi-Fi 分享器，答案是可以；若使用者問分享器怎麼連宿網或怎麼連宿舍網路，請優先說明 WAN 端接宿舍網路孔、進入分享器管理介面、WAN/網際網路設定選固定 IP，並填入申請宿網後取得的 IP 設定資訊；詳細可參考只列 https://net.nthu.edu.tw/netsys/faq:domitory_network_config2。
20. 宿網申請分成兩段：先在校務資訊系統申請「學生宿舍網路帳號」，再到宿網管理系統申請宿舍網路並取得 IP 設定資訊。回答「宿網要怎麼申請」時必須包含兩段，不可只停在帳號申請。
21. 回答「為什麼沒有宿網」或「宿網連不上」時，請分成尚未申請帳號、已申請帳號但尚未申請宿網、全部申請完成仍無法連線三種情況。
22. 回答「要怎麼設定宿舍網路」或「宿舍網路 IP 怎麼設定」時，只回答宿網 IP/TCP/IP 設定，不要重新說明宿網帳號申請流程，也不要列校務資訊系統帳密。不可說自動取得 DHCP；宿網 IP 設定應說明改成手動 IPv4，填入申請宿網後取得的 TCP/IP 設定。詳細可參考只列 https://net.nthu.edu.tw/netsys/faq:domitory_network_config。
23. 若資料中出現年度、學年度、新生申請時間或特定學號年份限制，必須以目前台灣日期判斷是否仍有效。每次問題提示會提供目前台灣日期與應採用的新生學號年份；過期公告除非使用者明確詢問歷史資訊，否則不要輸出。
24. 使用者問人社院、小吃部、風雲樓、水木生活中心、餐廳、院系館舍、公共區或其他校園地點「有沒有網路」時，應優先視為校園無線網路涵蓋範圍問題，主要參考 https://net.nthu.edu.tw/netsys/faq:wlan_range。除非使用者明確提到宿舍、宿網、宿舍網路孔或宿舍各齋住宿網路，否則不要提宿網、宿網申請或宿網信箱。若使用者一次問多個地點，必須逐一判斷；只有 FAQ 明確列出的校內公共區或系所單位可回答有，校外店家或資料未列出的地點不可概括回答有；若使用者已明確指出是校外餐廳或已知如紅吱吱牛排這類校外店家，應直接說不屬於清大校園無線網路涵蓋範圍。
25. 若目前問題是「我要怎麼連啊」「怎麼連」「要怎麼用」這類承接前文的追問，必須先看對話脈絡。若上一題是在問某校園地點有沒有網路，預設追問是在問該地點的校園無線網路連線方式，不要重新追問宿網或無線網路二選一。
26. 根據無線網路覆蓋圖，紅色範圍代表有校園無線網路覆蓋；若使用者問梅園有沒有網路，回答梅園不在目前可確認的紅色覆蓋範圍內，因此沒有清大校園無線網路覆蓋。可參考覆蓋圖：https://net.nthu.edu.tw/netsys/_media/wireless:wlan-cover-color.jpg?cache=
27. 網址必須完整複製可用資料中的 URL，不可縮寫、截斷、改寫網域或自行補網址。禁止輸出 https://net.n/、https://net.nthu...、https://net.nthu.edu.tw/n 這類不完整網址；若不確定完整 URL，就不要輸出該 URL。詳細可參考最多列 3 個網址。
28. 回答任何需要登入校務資訊系統的步驟時，不要說明校務資訊系統的預設帳號或預設密碼，例如不要寫「帳號為學號，預設密碼為身分證字號」。進入網路系統組線上服務時，請寫「在左方選單中點選『計通中心相關服務』裡的『網路系統組線上服務』」。
29. 說明無線網路外校漫遊帳號格式時，例子請寫 `s學號@wlan.nthu.edu.tw`，並補充「帳號會在校務資訊系統申請時產生或顯示」；不要使用 `u940001@wlan.nthu.edu.tw`。若只是申請 WiFi，不要要求使用者勾選啟用 VPN，請改寫為「VPN 可視個人需求開啟」。若回答校外漫遊，請寫「若使用 eduroam，需先在裝置 Wi-Fi 設定中點選 eduroam 連線並輸入無線網路帳號密碼，設定一次後每次到該網域附近時會自動連線」，不要一直強調 802.1X 認證。
30. 正文提到「校務資訊系統」時，只寫系統名稱，不要附上 `https://www.ccxp.nthu.edu.tw/ccxp/INQUIRE/`。回答排版保持簡潔：小標題用粗體文字即可，不要使用過大的 Markdown 標題。
31. 回答「校外連到學校網路」「設定學校 VPN」「VPN 怎麼設定」時，請回答學校 VPN，不要改問校內或校外，也不要回答宿網或一般無線認證。內容應分成「VPN 帳號申請與啟用」、「VPN 連線設定」、「尋求幫助」。需說明先啟用校園無線區域網路帳號的 VPN 功能：登入校務資訊系統，在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」，選擇「無線區域網路帳號」，填入資訊並在「VPN 設定」欄勾選「啟用」，完成後約 10 分鐘內生效。連線設定需說明下載 Ivanti Secure Access Client 或 Pulse Secure，下載連結為 `https://ndrive.niar.org.tw/navigate/a/#/s/894C6D3B91C94C3EB0D0B4237BC47B426BL`，安裝後點選「+」，「名稱」及「伺服器」皆填入 `nthu.twaren.net`，再用校園無線區域網路帳號與密碼驗證，帳號格式為 `XXXXXXX@wlan.nthu.edu.tw`。詳細可參考只列 `https://net.nthu.edu.tw/netsys/sslvpn:info`、`https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup`、`https://net.nthu.edu.tw/netsys/wireless:application:ccxp`。
"""

TRAINING_DATA_DIR = Path(__file__).resolve().parent / "training_data"
FEW_SHOT_SOURCES = (
    ("00_priority_expected_answers.jsonl", 40),
    ("01_specific_qa.jsonl", 60),
    ("02_clarifying_questions.jsonl", 20),
    ("03_out_of_scope.jsonl", 1),
    ("04_rag_grounded_answers.jsonl", 20),
    ("05_failure_rewrites.jsonl", 40),
    ("06_user_feedback_expected_answers.jsonl", 40),
    ("07_english_expected_answers.jsonl", 30),
)


def load_few_shot_examples() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []

    for filename, limit in FEW_SHOT_SOURCES:
        path = TRAINING_DATA_DIR / filename
        if not path.exists():
            continue

        loaded = 0
        with path.open(encoding="utf-8") as file:
            for line in file:
                if loaded >= limit:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue

                messages = row.get("messages", [])
                user_message = next((item.get("content", "") for item in messages if item.get("role") == "user"), "")
                assistant_message = next(
                    (item.get("content", "") for item in messages if item.get("role") == "assistant"),
                    "",
                )

                if not user_message or not assistant_message:
                    continue

                examples.append(
                    {
                        "type": row.get("type", "example"),
                        "language": row.get("language", "zh-Hant"),
                        "user": user_message,
                        "assistant": assistant_message,
                    }
                )
                loaded += 1

    return examples


def normalize_for_match(text: str) -> str:
    return " ".join(text.lower().replace("？", " ").replace("?", " ").split())


def example_score(question: str, example: dict[str, Any]) -> int:
    normalized_question = normalize_for_match(question)
    haystack = normalize_for_match(f"{example['user']} {example['assistant']} {example['type']}")
    score = 0

    for token in normalized_question.split():
        if len(token) >= 2 and token in haystack:
            score += 2

    important_terms = (
        "宿網", "宿舍", "分享器", "路由器", "無線", "wifi", "wi-fi", "eduroam",
        "nthu-cc", "nthupeap", "申請", "連不上", "梅園", "資電館", "小吃部",
        "人社院", "紅吱吱", "vpn", "密碼", "新生", "ip",
    )
    for term in important_terms:
        if term in normalized_question and term in haystack:
            score += 5

    type_boost = {
        "priority_expected_answer": 4,
        "user_feedback_expected_answer": 3,
        "failure_rewrite": 2,
    }
    return score + type_boost.get(str(example.get("type", "")), 0)


def select_few_shot_examples(question: str, language: str = "zh-Hant") -> list[dict[str, Any]]:
    examples = [example for example in load_few_shot_examples() if example.get("language") == language]
    ranked = sorted(
        examples,
        key=lambda example: example_score(question, example),
        reverse=True,
    )
    return ranked[:FEW_SHOT_MAX_EXAMPLES]


def build_few_shot_section(question: str, language: str = "zh-Hant") -> str:
    examples = select_few_shot_examples(question, language=language)
    if not examples:
        return ""

    lines = [
        "回答風格範例：",
        "以下只列出與目前問題較相關的少量範例；範例只用來學習回答方式，不可把範例中的內容當成目前問題的事實依據。",
    ]

    for index, example in enumerate(examples, start=1):
        lines.extend(
            [
                f"\n範例 {index}（{example['type']}）",
                f"學生：{example['user']}",
                f"助理：{example['assistant']}",
            ]
        )

    return "\n".join(lines)


def build_time_context() -> str:
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    freshman_year = now.year - 1911
    previous_years = ", ".join(str(year) for year in range(max(0, freshman_year - 3), freshman_year))
    return (
        f"時間判斷：目前台灣日期是 {now:%Y-%m-%d}。"
        f"今年 9 月開始是 {freshman_year} 學年度，因此目前新生學號年份應以 {freshman_year} 為準。"
        f"若資料提到過期的新生公告、舊申請日期或學號年份 {previous_years}，請略過，不要放進回答。"
    )


def build_user_prompt(question: str, context: str, history_context: str = "", language: str = "zh-Hant") -> str:
    few_shot_section = build_few_shot_section(question, language=language)
    time_context = build_time_context()
    language_instruction = (
        "Answer entirely in clear, natural English. Primarily use the official English sources for DormNet (https://net.nthu.edu.tw/netsys/en:faq#dormnet), wireless networking (https://net.nthu.edu.tw/netsys/en:faq#wireless_network), student email (https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std), Google Workspace / GApp account application (https://net.nthu.edu.tw/netsys/en:gapp#account_application_procedure), and the English FAQ (https://net.nthu.edu.tw/netsys/en:faq). Prefer English sources over Chinese sources whenever both cover the question. Translate Chinese source material only when the English documentation is insufficient. Preserve proper nouns, SSIDs, account formats, email addresses, and URLs exactly. In the answer, cite only complete English documentation URLs when suitable English pages are available. Every heading and structural label must also be English: use “Get Help” instead of “尋求幫助” and “For details” instead of “詳細可參考”. Do not output Chinese headings or labels in an English answer."
        if language == "en"
        else "請使用繁體中文回答。"
    )

    return f"""
/no_think
{few_shot_section}

現在請回答目前問題。

回答語言：
{language_instruction}

{time_context}

對話脈絡：
{history_context or "無"}

目前問題：
{question}

可用資料：
{context}

對話與服務隔離規則：
- 使用者目前明確指定的服務，優先於過去對話中的 topic。
- 除非使用者明確要求比較，否則不可混用校園 Wi-Fi、宿舍網路、VPN、Email 或帳號服務的資訊。
- 若可用資料明確屬於不同服務，不可使用該資料回答目前問題。
- 有相關且足夠的可用資料時不要不必要地拒答；必要資訊不足時則明確說明缺少什麼，不可臆測。

請直接給使用者可操作的答案，優先簡潔，避免不必要的長篇背景說明。
- 回答風格可以參考上方範例，但事實、網址、步驟、帳號格式與聯絡方式只能根據「可用資料」。
- 若資料中有步驟、帳號格式、SSID、登入方式、申請方式、下載項目或設定方式，請整理成具體步驟。
- 不要解釋你的推理過程。
- 不要在答案最後列出參考來源清單；來源會由介面另外顯示。不要寫「根據 FAQ」、「FAQ 顯示」、「依 FAQ」這類文字，直接說明答案。
- 若可用資料中有具體步驟，請直接輸出步驟；不要回答「請至某頁面找到某連結」這種轉介式說法。
- 回答最後可用「詳細可參考：」列出本次實際依據的精準頁面 URL；最多列 1 到 3 個最關鍵網址，不要把總入口頁當成主要參考。
- 詳細可參考的 URL 必須是完整可開啟的 `https://net.nthu.edu.tw/netsys/...` 網址。不可輸出 `https://net.n/`、`https://net.nthu...`、省略號或任何截斷網址。
- 所有網址必須獨立成行，而且該行只能包含網址本身。網址前後的說明、括號、密碼與標點必須移到其他行，避免超連結涵蓋後續回答。
- 排版保持緊湊：同一小節只用一個粗體標題，標題後直接接段落或步驟；不要連續輸出兩個標題，不要使用空白標題，不要在單一句子之間插入多餘空行。
- 編號項目若以簡短的「重點標籤：」開頭，請只將該前導標籤加粗，例如 `1. **確認連線來源：**後續說明`；同一編號內的短說明直接接在後面，不要拆成多個未縮排段落。英文回答亦使用相同格式。
- 若問題是校園無線網路使用，主要依據無線網路問題區與其精準頁面；詳細可參考最多列 3 個，例如 `https://net.nthu.edu.tw/netsys/faq:wlan_auth`、`https://net.nthu.edu.tw/netsys/faq:wlan_roaming`、`https://net.nthu.edu.tw/netsys/wireless:application`。
- 若問題是學生宿舍網路，主要依據學生宿舍網路問題區與宿網頁面；詳細可參考最多列 3 個，優先使用可用資料中的精準宿網 FAQ 頁與 `https://net.nthu.edu.tw/netsys/dormnet/`。
- 若問題是郵件、信箱、Webmail、SMTP、垃圾信或郵件記錄器，回答重點放在一般使用者需要的申請、登入、收信、寄信、容量與基本設定；優先提供簡單可操作的方法，避免不必要的伺服器或通訊協定細節。郵件相關回答不要加入「尋求幫助」段落，也不要提供任何聯絡信箱。主要依據 `https://net.nthu.edu.tw/netsys/mail:application_student:new_std`、`https://net.nthu.edu.tw/netsys/gapp#帳號申請流程` 與 `https://net.nthu.edu.tw/netsys/faq`；英文回答主要依據 `https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std`、`https://net.nthu.edu.tw/netsys/en:gapp#account_application_procedure` 與 `https://net.nthu.edu.tw/netsys/en:faq`，詳細可參考最多列 1 到 3 個網址。
- 若問題是校園無線網路使用，請同時區分校內使用、校外/外校漫遊、帳號申請。校內使用段落請照此語氣：`**瀏覽器登入（Web-based 認證）**`，對應 Wi-Fi 是 `nthu-cc` 或 `TANetRoaming`，連上 Wi-Fi 後打開瀏覽器，系統會自動跳出登入頁面，輸入無線網路帳號與密碼即可上網；`**WiFi 登入（設定一次即可）（802.1X + PEAP）**`，對應 Wi-Fi 是 `nthupeap` 或 `eduroam`，第一次在裝置 Wi-Fi 設定中輸入帳號與密碼，之後裝置就會自動連線，不需要每次重新登入。不要把這兩個認證方式做成過大的 Markdown 標題；請放在同一個「校內使用」標題下，並用粗體小標題呈現。不要在認證方式標題後加「適合手機、平板、電腦」或類似裝置適用性括號。申請 WiFi 時，VPN 僅寫「VPN 可視個人需求開啟」。只有在可用資料包含帳號格式時才提供帳號格式。
- 禁止使用項目符號（不要用 *、-、•）。不要巢狀列表；不要在編號項目下面再放子清單。如果需要補充，直接用短段落說明。
- 小標題必須寫成 `**標題**`，不要使用 `###` 這類過大的 Markdown 標題，也不要在小標題前加 1、2、3 或其他編號；只有真正的操作步驟才使用 1、2、3 編號。
- 正文提到「校務資訊系統」時，只寫系統名稱，不要附上 `https://www.ccxp.nthu.edu.tw/ccxp/INQUIRE/`。
- 操作型問題不要把狀態頁、流量圖、MRTG、status、traffic 連結放進正文；這些不是教學連結。
- 若資料中出現過去年份的新生申請公告、已過期日期或特定舊入學年度限制，請依上方「時間判斷」判斷是否仍有效。若資料提到舊年份的新生公告或過期學號年份，請略過，不要放進回答。
- 若使用者問人社院、小吃部、風雲樓、水木生活中心、餐廳、院系館舍、公共區或其他校園地點「哪裡有網路 / 有沒有網路 / 能不能上網 / 有沒有 Wi-Fi」，只回答校園無線網路涵蓋範圍與該地點是否可用；不要直接切到「怎麼連」教學，也不要把 Web-based 認證、802.1X + PEAP 認證放進答案，除非使用者明確追問怎麼連。除非使用者明確提到宿舍、宿網、宿舍網路孔或宿舍各齋住宿網路，否則不要提宿網、宿網申請、宿網帳號或宿網信箱。若同一句包含多個地點，請逐一列出判斷：有列出的校內地點可說有；校外店家或資料未列出的地點不要一起概括為有；若使用者已明確指出是校外餐廳或已知如紅吱吱牛排這類校外店家，請直接回答不屬於清大校園無線網路涵蓋範圍。詳細可參考列 `https://net.nthu.edu.tw/netsys/faq:wlan_range` 與 `https://net.nthu.edu.tw/netsys/wireless:easy`。
- 若目前問題是「我要怎麼連啊」「怎麼連」「要怎麼用」等短追問，請先看對話脈絡。若上一題是在問校園地點是否有網路，直接延續為校園無線網路連線方式，回答 nthu-cc/TANetRoaming 與 nthupeap/eduroam 的連線方式，不要再問宿網或無線網路。
- 若使用者問「梅園有網路嗎」，請回答梅園沒有清大校園無線網路覆蓋，依據是無線網路覆蓋圖紅色範圍；詳細可參考：https://net.nthu.edu.tw/netsys/_media/wireless:wlan-cover-color.jpg?cache=
- 若問題是 VPN、SSLVPN、校外連線到學校網路或校內資源，請分成「VPN 帳號申請與啟用」、「VPN 連線設定」、「尋求幫助」。不要回答 Juniper SSL-VPN、TWAREN SSL-VPN 二選一，也不要把無線認證或宿網設定當成主要答案。VPN 詳細可參考只列 `https://net.nthu.edu.tw/netsys/sslvpn:info`、`https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup`、`https://net.nthu.edu.tw/netsys/wireless:application:ccxp`。
- 聯絡方式只分三種情況：無線網路與 VPN 問題使用 wlan@cc.nthu.edu.tw；學生宿舍網路問題使用 dorms@cc.nthu.edu.tw；與網路系統組無關的問題不得提供聯絡方式。禁止輸出「待定」。若需要協助段落，輸出 `**尋求幫助**`，下一行只接一個完整說明段落。
- 若資料不足，直接說明缺少哪些資訊，不要附上未知或「待定」的聯絡方式。
"""
