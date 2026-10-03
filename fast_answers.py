
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from agent.semantics import extract_location_slot, is_network_availability_request
from wireless_coverage import build_coverage_response
from utils import clean_answer


def normalize_text(text: str) -> str:
    return re.sub(r"[\s　，,。．.？?！!：:；;、（）()「」『』\[\]【】\-_/\'’]+", "", text.lower())


def source(title: str, url: str, content: str) -> dict[str, Any]:
    return {"title": title, "source_name": title, "url": url, "content": content, "chunk_index": 0, "score": 1.0}


TRAINING_DATA_DIR = Path(__file__).resolve().parent / "training_data"
TRAINING_FAST_FILES = ("00_priority_expected_answers.jsonl", "06_user_feedback_expected_answers.jsonl")
META_ANSWER_PREFIXES = ("請不要", "AI 應", "期望回答", "不能直接回答", "問「", "若回答 nthupeap", "這題", "第二題要", "請依照", "換宿後宿網申請回答")


def split_user_variants(text: str) -> list[str]:
    parts = re.split(r"[\n/／]|或者是問|或問|或是問|或者|或", text)
    return [part.strip(" ：:？?。\t") for part in parts if part.strip(" ：:？?。\t")]


def answer_urls(answer: str) -> list[str]:
    urls = []
    for url in re.findall(r"https://[^\s<>)）]+", answer):
        clean_url = url.rstrip("。。，,.;；")
        if clean_url not in urls:
            urls.append(clean_url)
    return urls[:3]


def sources_from_answer(answer: str) -> list[dict[str, Any]]:
    source_text = answer.split("詳細可參考", 1)[1] if "詳細可參考" in answer else answer
    urls = answer_urls(source_text)
    if not urls:
        return [source("https://net.nthu.edu.tw/netsys/faq", "https://net.nthu.edu.tw/netsys/faq", "")]
    return [source(url, url, "") for url in urls]


def is_meta_answer(answer: str) -> bool:
    stripped = answer.strip()
    if any(stripped.startswith(prefix) for prefix in META_ANSWER_PREFIXES):
        return True
    meta_phrases = (
        "回答時",
        "需完整說明",
        "需先提醒",
        "主要依據",
        "不要被 guard",
        "不要被擋",
        "答案需",
        "請主要依據",
    )
    return any(phrase in stripped[:180] for phrase in meta_phrases)


@lru_cache(maxsize=1)
def load_training_fast_answers() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for filename in TRAINING_FAST_FILES:
        path = TRAINING_DATA_DIR / filename
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                messages = row.get("messages", [])
                user_message = next((item.get("content", "") for item in messages if item.get("role") == "user"), "")
                assistant_message = next((item.get("content", "") for item in messages if item.get("role") == "assistant"), "")
                if not user_message or not assistant_message or is_meta_answer(assistant_message):
                    continue
                variants = [normalize_text(variant) for variant in split_user_variants(user_message)]
                variants = [variant for variant in variants if len(variant) >= 5]
                if variants:
                    variants = sorted(set(variants), key=len, reverse=True)
                    examples.append({"variants": variants, "answer": assistant_message})
    return examples


def get_training_fast_answer(question: str, *, exact_only: bool = False) -> tuple[str, list[dict[str, Any]]] | None:
    normalized = normalize_text(question)
    if len(normalized) < 5:
        return None

    examples = load_training_fast_answers()
    for example in examples:
        for variant in example["variants"]:
            if normalized == variant:
                answer = example["answer"]
                return answer, sources_from_answer(answer)

    if exact_only:
        return None

    for example in examples:
        for variant in example["variants"]:
            if variant in normalized or normalized in variant:
                answer = example["answer"]
                return answer, sources_from_answer(answer)
    return None


WIRELESS_SOURCES = [
    source("faq:wlan_auth [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:wlan_auth", "無線網路認證方式包含 Web-based 認證與 802.1X + PEAP 認證。"),
    source("faq:wlan_roaming [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:wlan_roaming", "外校漫遊使用 TANetRoaming 或 eduroam，帳號後需加 @wlan.nthu.edu.tw。"),
    source("wireless:application [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application", "校園無線區域網路帳號可透過校務資訊系統申請。"),
]

VPN_SOURCES = [
    source("sslvpn:info [網路系統組]", "https://net.nthu.edu.tw/netsys/sslvpn:info", "TWAREN SSL VPN 服務資訊與連線說明。"),
    source("sslvpn:sslvpn_setup [網路系統組]", "https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup", "VPN 軟體安裝與設定說明。"),
    source("wireless:application:ccxp [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application:ccxp", "校園無線區域網路帳號申請與 VPN 啟用步驟。"),
]

DORM_APPLY_SOURCES = [
    source("faq:domitory_net_ua_apply [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply", "宿網帳號申請步驟。"),
    source("faq:domitory_net_apply [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:domitory_net_apply", "學生宿舍網路申請與每日 10 時、16 時系統處理。"),
    source("dormnet [網路系統組]", "https://net.nthu.edu.tw/netsys/dormnet/", "學生宿舍網路服務入口。"),
]

DORM_CONFIG_SOURCES = [
    source("faq:domitory_network_config [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:domitory_network_config", "宿網 TCP/IP 設定需改為手動 IPv4，填入申請後取得的設定。"),
]

DORM_ROUTER_SOURCES = [
    source("faq:domitory_network_config2 [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:domitory_network_config2", "分享器連接宿舍網路時，WAN 端接宿舍網路孔並設定固定 IP。"),
]

DORM_USELESS_SOURCES = [
    source("faq:domitory_net_useless [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:domitory_net_useless", "宿網突然不通時可查詢封鎖、禁用、設備埠狀態並做交叉測試。"),
    source("dormnet [網路系統組]", "https://net.nthu.edu.tw/netsys/dormnet/", "學生宿舍網路服務與查詢入口。"),
]

DORM_IP_LOOKUP_SOURCES = [
    source("DormNet IP status [網路系統組]", "https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl", "宿網申請狀態與 IP/TCP/IP 設定資訊查詢。"),
    source("faq:domitory_net_useless [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:domitory_net_useless", "宿網突然不通時可查詢封鎖、禁用、設備埠狀態並做交叉測試。"),
]

DORM_BUILDING_TERMS = (
    "明齋", "平齋", "清齋", "華齋", "誠齋", "義齋", "新齋", "禮齋",
    "仁齋", "實齋", "信齋", "碩齋", "學齋", "儒齋", "文齋", "靜齋",
    "慧齋", "雅齋", "鴻齋", "善齋", "鳴鳳樓", "崇善樓", "迎曦軒",
    "掬月齋", "樹德樓",
)

EN_DORM_BUILDING_TERMS = (
    "ruzhai", "ruzai", "rudorm", "rudormitory", "ruresidencehall",
    "xinzhai", "xinzai", "xindorm", "xindormitory", "xinresidencehall",
    "mingzhai", "pingzhai", "qingzhai", "huazhai", "chengzhai", "yizhai",
    "renzhai", "shizhai", "shuozhai", "xuezhai", "wenzhai", "jingzhai",
    "huizhai", "yazhai", "hongzhai", "shanzhai",
)

WLAN_RANGE_SOURCES = [
    source("faq:wlan_range [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:wlan_range", "校園無線網路涵蓋範圍包含公共區與部分系所單位。"),
    source("wireless:easy [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:easy", "無線上網使用說明。"),
]

WIRELESS_TROUBLESHOOTING_SOURCES = [
    source("faq:wlan_useless [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:wlan_useless", "校園無線網路無法使用時的排除方式。"),
]

EMAIL_APPLICATION_SOURCES = [
    source("mail:application_student:new_std [網路系統組]", "https://net.nthu.edu.tw/netsys/mail:application_student:new_std", "學生電子郵件信箱申請步驟。"),
    source("gapp [網路系統組]", "https://net.nthu.edu.tw/netsys/gapp#帳號申請流程", "Google Workspace / gapp 帳號申請流程。"),
]


WIRELESS_ANSWER = """校園無線網路可以分成校內使用、外校漫遊與帳號申請來看。

**校內使用**
**瀏覽器登入（Web-based 認證）**
對應的 Wi-Fi 名稱是 `nthu-cc` 或 `TANetRoaming`。連上 Wi-Fi 後，打開瀏覽器，系統會自動跳出登入頁面，輸入無線網路帳號與密碼即可上網。

**WiFi 登入（設定一次即可）（802.1X + PEAP）**
對應的 Wi-Fi 名稱是 `nthupeap` 或 `eduroam`。第一次使用時，在裝置的 Wi-Fi 設定中輸入帳號與密碼，之後裝置會自動連線，不需要每次重新登入。

**外校漫遊**
若人在其他有加入漫遊的大學，請尋找 `TANetRoaming` 或 `eduroam`。使用清大帳號登入時，帳號後面要加上 `@wlan.nthu.edu.tw`，例如 `s學號@wlan.nthu.edu.tw`。這個帳號會在校務資訊系統申請無線網路帳號時產生或顯示。

**申請無線網路帳號**
1. 登入校務資訊系統。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 選擇左方選單的「無線區域網路帳號」進行申請。
4. 設定無線網路帳號密碼。VPN 不一定要開，可視個人需求開啟。

此申請頁需要從校內 IP 連線才能使用。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/wireless:application"""

WIRELESS_APPLICATION_ANSWER = """**申請無線網路帳號**

1. 登入校務資訊系統。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 選擇左方選單的「無線區域網路帳號」進行申請。
4. 設定無線網路帳號密碼。VPN 不一定要開，可視個人需求開啟。

此申請頁需要從校內 IP 連線才能使用。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/wireless:application:ccxp"""


VPN_DOWNLOAD_VERSION_ANSWER = """下載網址裡的 `22.7R2.4`、`22.7R2.6`、`22.7R2.8`、`9.1R14`、`9.1R17` 這些資料夾名稱是 VPN 連線軟體的各版本號。

**接下來怎麼選**
1. 先選一個較新的版本資料夾進去。
2. 進入資料夾後，再依自己的作業系統選 Windows、macOS 或其他對應安裝檔下載。
3. 若同時看到很多版本，但學校說明頁沒有指定版本，通常可以優先選較新的版本；若不確定，請提供作業系統與資料夾截圖向無線網路服務信箱確認。
4. 安裝完成後，回到 VPN 軟體設定：伺服器填 `nthu.twaren.net`，帳號格式為 `s學號@wlan.nthu.edu.tw`。

**尋求幫助**
若不確定該下載哪個版本，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供你的作業系統、目前看到的資料夾或檔名截圖，以便技術人員協助確認。

詳細可參考：
https://net.nthu.edu.tw/netsys/sslvpn:info
https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup"""


VPN_PASSWORD_ANSWER = """VPN 軟體登入時，密碼請填「校園無線區域網路帳號」的密碼，也就是你在校務資訊系統的網路系統組頁面中設定的無線網路帳號密碼。

**在哪裡設定或確認**
1. 登入「校務資訊系統」。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 選擇「無線區域網路帳號」。
4. 在該頁面申請或重新設定無線網路帳號密碼。
5. 設定完成後，通常約 10 分鐘內生效。

VPN 軟體登入時，帳號格式為 `s學號@wlan.nthu.edu.tw`，密碼則填上面設定的無線網路帳號密碼。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application:ccxp
https://net.nthu.edu.tw/netsys/sslvpn:info"""

VPN_OPTIONAL_ANSWER = """不用。若只是要使用校園 Wi-Fi，VPN 不一定要開。

VPN 是在校外連回清大校內網路資源時才需要，可視個人需求開啟。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application:ccxp
https://net.nthu.edu.tw/netsys/sslvpn:info"""

NTHU_CC_SWITCH_WIFI_ANSWER = """如果你連上 `nthu-cc` 但登入頁一直跳不出來，可以先改試下面幾個 Wi-Fi：

1. `TANetRoaming`：同樣是瀏覽器登入，連上後打開瀏覽器，看是否會導到登入頁。
2. `nthupeap` 或 `eduroam`：在裝置的 Wi-Fi 設定中輸入無線網路帳號密碼，設定完成後之後會自動登入。

若你只是想快速排除問題，建議先試 `TANetRoaming`；若希望之後不用每次開瀏覽器登入，可以改設定 `nthupeap` 或 `eduroam`。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/wireless:easy"""

GAPP_EFFECTIVE_ANSWER = """目前資料沒有明確列出 G Suite for Education（gapp）帳號申請完成後多久可以使用。

建議你申請送出後先稍等一段時間再測試登入；若仍無法使用，請依 gapp 頁面提供的聯絡方式或網路系統組相關服務詢問承辦人員，並附上申請時間、帳號或畫面截圖，方便確認申請狀態。

詳細可參考：
https://net.nthu.edu.tw/netsys/gapp#帳號申請流程"""

EXTERNAL_EDUROAM_FAILURE_ANSWER = """在外校使用 `eduroam` 一直登入失敗時，請先從帳號格式、密碼與現場漫遊服務確認。

**先確認帳號密碼**
1. 帳號請輸入 `s學號@wlan.nthu.edu.tw`。
2. 密碼是清大校園無線區域網路帳號的密碼，不一定是校務資訊系統密碼。
3. 如果剛改過密碼，請等約 10 分鐘後再試。

**再確認裝置設定**
1. 在裝置 Wi-Fi 設定中忘記或刪除原本儲存的 `eduroam`。
2. 重新選擇 `eduroam`，再輸入完整帳號與密碼。
3. 確認帳號中的英文字母皆為小寫。

**確認外校環境**
1. 確認該校現場確實有提供 `eduroam` 漫遊。
2. 若同一地點訊號弱或一直失敗，建議換到該校訊號較好的位置再測試。

**尋求幫助**
若仍失敗，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在學校、SSID、裝置系統、帳號格式、錯誤訊息與截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/faq:wlan_useless"""

DORM_REPAIR_EMAIL_INFO_ANSWER = """寄信給宿網信箱報修時，建議一次附上下面資料，技術人員會比較容易判斷是否為網路孔、線路或設備問題。

**寄信對象：**請寄到宿網信箱 `dorms@cc.nthu.edu.tw`。

**信中請提供**
1. 宿舍名稱與房號。
2. 疑似故障的網路孔位置。
3. 問題狀況，例如完全無法連線、時好時壞、網路孔燈號異常等。
4. 交叉測試結果，例如同一台電腦與網路線接到其他房間是否可用、室友電腦接你的網路孔是否也無法使用。
5. 是否已確認使用該網路孔對應的宿網 IP 設定。
6. IP 設定畫面、錯誤訊息、網路狀態、網路孔或網路線連接狀況截圖，附圖佳。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""

WIRELESS_APPLICATION_PAGE_ANSWER = """無線網路申請頁無法進入時，請依序確認以下狀況：

**確認是否從校內 IP 連線**
1. 申請頁面僅限校內 IP 使用。
2. 若人在校外，請先連上學校 VPN 後再嘗試開啟。

**若已從校內連線但仍無法進入**
1. 重新登入校務資訊系統。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 重新點選右方出現的「登入網路系統組線上服務」連結。
4. 若出現 `Cannot get checksum or expired`，通常表示連結已超過約 2 分鐘有效時間，請重新產生連結。
5. 若出現 `IP mismatch`，表示目前來源 IP 與登入校務資訊系統時不同，請確認網路環境後重新登入。

**尋求幫助**
若仍無法進入，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供裝置系統、所在位置、目前網路來源、錯誤訊息與截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/wireless:application:ccxp"""

WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER = """目前清大校園無線網路沒有建議作為正式上網用途的「不用帳號密碼」連線方式。

**先釐清 Wi-Fi 名稱**
1. `nthu-cc` 和 `TANetRoaming` 是瀏覽器登入，看起來不需要額外設定，但連上後仍需要輸入校園無線區域網路帳號與密碼。
2. `nthupeap` 和 `eduroam` 是 WiFi 登入，第一次連線時也需要輸入校園無線區域網路帳號與密碼。
3. 若現場看到其他看似免費或免帳密的 Wi-Fi，通常不應直接視為清大網路系統組提供的正式校園網路。

如果你現在是因為還沒有帳號密碼而無法使用學校網路，還是需要先完成無線網路帳號申請；若申請頁無法進入，請確認是否在校內 IP 環境，人在校外時可先連 VPN 後再試。若仍無法處理，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 說明你無法進入申請頁、目前所在位置與畫面截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:easy
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/wireless:application:ccxp"""


EN_WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER = """NTHU campus Wi-Fi does not provide a recommended official no-account/no-password connection for normal Internet use.

**Check the Wi-Fi names first**
1. `nthu-cc` and `TANetRoaming` use browser login. They do not require extra Wi-Fi profile setup, but you still need a campus wireless LAN account and password after connecting.
2. `nthupeap` and `eduroam` use WiFi login. They also require a campus wireless LAN account and password when you set them up.
3. If you see another Wi-Fi name that looks free or does not ask for credentials, do not assume it is an official NTHU Network Systems Division service.

If you cannot use the school network because you do not have the account yet, you still need to apply for a campus wireless LAN account first. If the application page will not open, make sure you are using an on-campus IP; if you are off campus, connect to the NTHU VPN first and try again. If it still fails, contact wlan@cc.nthu.edu.tw with your location, screenshot, and the page you cannot open.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:easy
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp"""


WIRELESS_NO_CREDENTIAL_SOURCES = [
    source("wireless:easy [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:easy", "清大校園無線網路使用方式。"),
    source("wireless:application [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application", "校園無線區域網路帳號申請。"),
    source("wireless:application:ccxp [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application:ccxp", "校務資訊系統申請無線區域網路帳號步驟。"),
]

EN_WIRELESS_NO_CREDENTIAL_SOURCES = [
    source("en:wireless:easy [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:easy", "NTHU campus wireless usage."),
    source("en:wireless:application [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application", "Campus wireless LAN account application."),
    source("en:wireless:application:ccxp [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp", "Wireless application via Academic Information System."),
]


def is_wireless_application_page_intent(question: str) -> bool:
    normalized = normalize_text(question)
    has_page = any(term in normalized for term in ("申請頁", "申請頁面", "申請網路頁面", "申請網路的頁面", "網路申請頁", "網路申請頁面", "applicationpage", "applicationform", "applicationwebsite"))
    has_network = any(term in normalized for term in ("無線", "wifi", "wi-fi", "wify", "學校網路", "校園網路", "網路", "wireless", "campuswifi", "campusnetwork"))
    has_problem = any(term in normalized for term in ("進不去", "打不開", "無法進入", "開不了", "不能開", "不能進", "連不進去", "cannotopen", "cantopen", "wontopen", "willnotopen", "cannotaccess", "cantaccess"))
    return has_page and has_network and has_problem


def is_no_credential_network_intent(question: str) -> bool:
    normalized = normalize_text(question)
    has_network = any(term in normalized for term in ("學校網路", "校園網路", "無線", "wifi", "wi-fi", "wify", "網路", "nthucc", "nthu-cc", "tanetroaming", "campuswifi", "campuswi-fi", "campusnetwork", "schoolnetwork", "wireless"))
    no_credential = any(term in normalized for term in ("不用帳密", "不用帳號", "不用密碼", "不需要帳密", "不需要帳號", "不需要密碼", "免帳密", "免帳號", "免密碼", "沒有帳號", "還沒帳號", "還沒有帳號", "還沒拿到帳號", "還沒拿到帳號密碼", "還沒拿到帳密", "沒有密碼", "還沒密碼", "還沒有密碼", "沒有帳號密碼", "不想先辦帳密", "不想辦帳密", "不用登入", "免登入", "無需登入", "withoutaccount", "withoutanaccount", "withoutpassword", "withoutapassword", "withoutanaccountorpassword", "withoutaccountorpassword", "withoutlogin", "withoutloggingin", "nopassword", "noaccount", "noaccountorpassword", "freewifi", "guestwifi", "guestnetwork"))
    seeking = any(term in normalized for term in ("哪裡", "哪個", "有沒有", "有", "嗎", "嘛", "可以", "可不可以", "能不能", "怎麼辦", "找", "使用", "連", "where", "which", "isthere", "canuse", "connect", "use"))
    return has_network and no_credential and seeking


def has_network_failure_intent(question: str) -> bool:
    normalized = normalize_text(question)
    return any(term in normalized for term in (
        "不能用", "無法使用", "不能上網", "上不了網", "無法上網", "沒網路", "沒有網路",
        "連不上", "連不到", "無法連線", "連線失敗", "不通", "斷線", "一直斷",
        "不穩", "很慢", "很卡", "很差", "怪怪", "異常", "故障", "有點問題", "有問題", "出問題", "轉圈", "轉不出來", "跑不動",
        "掛了", "死掉", "沒反應", "網頁開不了", "網頁打不開", "網頁載不出來",
        "載不出來", "載不動", "動不了", "打不開", "開不出來", "有連上但不能用",
        "cannotconnect", "cantconnect", "unabletoconnect", "wontconnect",
        "doesnotconnect", "doesntconnect", "connectionfailed", "loginfailed",
        "doesnotwork", "doesntwork", "isnotworking", "notworking", "notwork",
        "nointernet", "cannotgetonline", "cantgetonline", "keepsdisconnecting",
        "disconnecting", "unstable", "veryslow", "slowconnection", "poorsignal",
    ))


def is_wireless_network_issue_intent(question: str) -> bool:
    normalized = normalize_text(question)
    has_wireless_service = any(term in normalized for term in (
        "無線網路", "校園無線", "校園wifi", "學校wifi", "wifi", "wify",
        "wireless", "wirelesslan", "wirelessnetwork", "campuswifi", "campusnetwork",
        "nthucc", "nthupeap", "tanetroaming", "eduroam",
    ))
    return has_wireless_service and has_network_failure_intent(question)


def is_dorm_network_context(question: str) -> bool:
    normalized = normalize_text(question)
    if any(term in normalized for term in ("宿網", "宿舍網路", "學生宿舍網路", "dormnet", "dormitorynetwork", "dormnetwork")):
        return True
    has_dorm_topic = any(term in normalized for term in ("宿舍", "寢室", "房間", "網路孔", "網孔")) or any(term in question for term in DORM_BUILDING_TERMS)
    has_network = any(term in normalized for term in ("網路", "網路孔", "網孔", "上網", "連線", "連", "wifi", "wi-fi", "ip", "帳號", "密碼", "帳密"))
    return has_dorm_topic and has_network


def is_dorm_network_issue_intent(question: str) -> bool:
    normalized = normalize_text(question)
    if not is_dorm_network_context(question):
        return False
    if any(term in normalized for term in ("申請", "登錄", "註冊", "怎麼辦理", "怎麼申請", "哪裡申請")) and not any(term in normalized for term in ("進不去", "不能用", "連不上", "不穩", "很慢", "很卡", "怪怪")):
        return False
    return any(term in normalized for term in (
        "不能用", "無法用", "不能上網", "無法上網", "沒網路", "沒有網路", "突然沒網路",
        "連不上", "連不到", "無法連線", "連線失敗", "不通", "斷線", "一直斷", "會斷", "掉線",
        "不穩", "很不穩", "不太穩", "不太好", "網路不好", "怪怪", "異常",
        "很慢", "慢", "超慢", "很卡", "超卡", "卡卡", "很爛", "超爛", "網路爛", "品質不好",
        "今天", "最近", "前幾天", "上禮拜", "上週", "怎麼辦", "什麼問題"
    ))


def is_dorm_ip_lookup_intent(question: str) -> bool:
    normalized = normalize_text(question)
    if not is_dorm_network_context(question) or "ip" not in normalized:
        return False
    setting_terms = ("設定", "怎麼設定", "怎麼設", "填", "手動", "固定ip", "tcpip", "乙太網路", "set", "setup", "configure", "staticip")
    lookup_terms = (
        "忘記", "忘了", "不記得", "查", "查詢", "查看", "看", "找", "找回", "在哪", "哪裡",
        "申請到", "拿到", "取得", "目前", "myapstatus", "status", "lookup", "check", "find", "forgot",
    )
    if any(term in normalized for term in lookup_terms):
        return True
    return not any(term in normalized for term in setting_terms) and any(term in normalized for term in ("狀態", "狀況"))


def is_dorm_ip_status_intent(question: str) -> bool:
    normalized = normalize_text(question)
    if not is_dorm_network_context(question):
        return False
    if is_dorm_ip_lookup_intent(question):
        return False
    status_terms = (
        "ip狀態", "ip狀況", "狀態", "狀況", "禁用", "被禁用", "封鎖", "被封鎖", "停用", "被停用",
        "異常", "查狀態", "狀態查詢", "網路異常", "不能用", "無法上網", "連不上", "不通",
        "disabled", "blocked", "banned", "status", "abnormal", "notworking", "cannotconnect",
    )
    return any(term in normalized for term in status_terms) and any(term in normalized for term in ("ip", "狀態", "禁用", "封鎖", "停用", "異常", "disabled", "blocked", "status"))


def is_dorm_network_account_intent(question: str) -> bool:
    normalized = normalize_text(question)
    if not is_dorm_network_context(question):
        return False
    return any(term in normalized for term in ("帳號密碼", "帳密", "帳號", "密碼")) and not any(term in normalized for term in ("未申請完成", "沒申請完成", "忘記學校", "無線", "wifi", "wi-fi"))


def is_dorm_network_availability_intent(question: str) -> bool:
    normalized = normalize_text(question)
    if not is_dorm_network_context(question):
        return False
    if is_dorm_network_issue_intent(question):
        return False
    return any(term in normalized for term in ("有網路嗎", "有宿網嗎", "有沒有網路", "有沒有宿網", "是否有網路", "提供網路", "可以用網路嗎"))


EDUROAM_ROAMING_ACCOUNT_ANSWER_ZH = """在外校使用 `eduroam` 漫遊時，帳號請輸入：

`s學號@wlan.nthu.edu.tw`

密碼是你申請清大校園無線區域網路帳號時設定的密碼，不一定是校務資訊系統密碼。

如果是在清大校內使用 `eduroam` 或 `nthupeap`，帳號通常只要輸入 `s學號`。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/faq:wlan_auth"""

AMBIGUOUS_NETWORK_ANSWER = """我需要先確認你是遇到哪一種清大網路問題，才能給你正確步驟。

請補充下面資訊：
1. 使用的服務：宿網、校園 Wi-Fi、VPN、信箱，或其他清大網路服務。
2. 所在位置：例如宿舍名稱與房號、物理館、台達館、圖書館等。
3. 連線方式或名稱：例如網路線、`nthu-cc`、`TANetRoaming`、`nthupeap`、`eduroam`。
4. 具體狀況：連不上、很慢、登入失敗、登入頁跳不出來、IP 設定錯誤，或錯誤訊息截圖。

你也可以直接描述成：「我在某地，用某個 Wi-Fi / 宿網，出現某個錯誤」。"""

NETWORK_SERVICE_SELECTION_ANSWER = """可以依所在位置與用途選擇服務：

**宿網**是在學生宿舍房間使用網路線連接的有線網路，需先完成宿網申請並設定取得的固定 IP。

**校園 Wi-Fi**是在校內教室、公共區或系館使用 `nthu-cc`、`nthupeap`、`TANetRoaming` 或 `eduroam` 無線上網。

**VPN**是人在校外、需要連回僅限校內 IP 使用的清大資源時使用；一般校內上網不需要先開 VPN。"""


DORM_UNIDENTIFIED_NETWORK_ANSWER = """若宿網 IP 已設定完成，但 Windows 顯示「無法辨識的網路」，可以重新安裝或重新掃描乙太網路介面卡。

1. 開啟「裝置管理員」，找到乙太網路使用的網路介面卡。
2. 解除安裝該乙太網路介面卡。
3. 執行「掃描硬體變更」，讓 Windows 重新偵測網路介面卡。
4. 重新填入宿網申請後取得的 TCP/IP 設定，再測試連線。

若仍無法排除，請向 dorms@cc.nthu.edu.tw 提供宿舍房號、IP 設定與錯誤畫面。

詳細可參考：https://net.nthu.edu.tw/netsys/faq:domitory_network_adapter_reinstall"""

DORM_SUPPORT_CONTACT_ANSWER = """宿舍有線網路、宿網、宿舍網路孔或宿網 IP 設定故障，請聯絡宿網信箱：

dorms@cc.nthu.edu.tw

寄信時請附上宿舍與房號、裝置系統、IP 設定、錯誤訊息及相關截圖。"""


DORM_CROSS_TEST_ESCALATION_ANSWER = """交叉測試已經顯示：其他人的電腦或裝置接到同一個房間網路孔也無法連線，問題較可能在房間網路孔、線路或宿網設備端，不需要再重複前面的交叉測試。

請寄信到宿網服務信箱：

dorms@cc.nthu.edu.tw

寄信時請附上：
1. 宿舍名稱與房號。
2. 交叉測試結果，包括測試的裝置、網路線與網路孔。
3. 宿網 IP 設定與狀態查詢結果。
4. 發生時間、錯誤訊息及相關截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""


NETWORK_SUPPORT_CONTACTS_ANSWER = """清大網路相關問題可依服務類型聯絡不同信箱：

**校園無線網路 / Wi-Fi**
請聯絡無線網路服務信箱：wlan@cc.nthu.edu.tw

來信時建議提供所在位置、連線的 SSID（例如 `nthu-cc`、`nthupeap`、`TANetRoaming`、`eduroam`）、裝置系統、錯誤訊息與截圖。

**宿舍網路 / 宿網**
請聯絡宿網信箱：dorms@cc.nthu.edu.tw

來信時建議提供宿舍與房號、裝置系統、是否有設定 IP、IP 設定畫面、網路狀況與錯誤訊息截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_useless
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""

VPN_INTERNAL_IP_ANSWER = """如果人在家中或校外，需要存取僅限校內 IP 才能使用的清大服務，應使用學校 VPN 連回校內網路。

**處理方式**
1. 先確認你已申請校園無線區域網路帳號，並視需求啟用 VPN。
2. 依作業系統下載並安裝 Ivanti Secure Access Client 或 Pulse Secure。
3. VPN 伺服器填入 `nthu.twaren.net`。
4. 使用校園無線區域網路帳號與密碼登入，帳號格式為 `s學號@wlan.nthu.edu.tw`。
5. 連線成功後，再開啟原本僅限校內 IP 的服務。

**尋求幫助**
若 VPN 無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供作業系統、VPN 軟體名稱、帳號格式、錯誤訊息與截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/sslvpn:info
https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup
https://net.nthu.edu.tw/netsys/wireless:application:ccxp"""

DORM_WIRED_NETWORK_SELECTION_ANSWER = """在宿舍房間使用「有線網路」時，應申請宿舍網路，也就是宿網。

**怎麼選**
1. 宿舍房間接網路線使用：申請宿網。
2. 校內公共區、教室或系館使用無線上網：申請校園 Wi-Fi。
3. 人在校外要連回僅限校內 IP 的服務：使用 VPN。

**宿網申請重點**
1. 先在校務資訊系統左方選單點選「計通中心相關服務」裡的「網路系統組線上服務」。
2. 申請「學生宿舍網路帳號」並設定宿網密碼。
3. 接著到宿舍網路申請頁面填寫宿舍資料，取得宿網 IP 設定資訊。
4. 申請完成後，每日 10 時與 16 時系統處理完畢後即可使用。
5. 使用電腦直接接宿舍網路線時，需依取得的 TCP/IP 資訊設定宿網 IP。

若不確定 IP 怎麼設定，可以接著問「宿網 IP 要怎麼設定」。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/faq:domitory_net_apply
https://net.nthu.edu.tw/netsys/dormnet/"""

WIRELESS_CONNECT_FOLLOWUP_ANSWER = """可以直接連清大校園無線網路，常用方式如下：

**瀏覽器登入（Web-based 認證）**
對應的 Wi-Fi 名稱是 `nthu-cc` 或 `TANetRoaming`。連上 Wi-Fi 後打開瀏覽器，系統會帶出登入頁面，輸入無線網路帳號與密碼即可上網。

**WiFi 登入（設定一次即可）（802.1X + PEAP）**
對應的 Wi-Fi 名稱是 `nthupeap` 或 `eduroam`。第一次使用時，在裝置的 Wi-Fi 設定中輸入無線網路帳號與密碼，完成後裝置之後會自動連線。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/wireless:easy"""

ROAMING_ANSWER = """校外漫遊是指人在其他有加入漫遊的大學時，可以使用清大的無線網路帳號登入該校可漫遊的 Wi-Fi。

**外校漫遊**
1. 到其他有加入漫遊的大學時，先搜尋 `TANetRoaming` 或 `eduroam`。
2. 若使用 `eduroam`，需先在裝置 Wi-Fi 設定中點選 `eduroam` 連線並輸入無線網路帳號密碼。
3. 帳號格式請使用 `s學號@wlan.nthu.edu.tw`，帳號會在校務資訊系統申請時產生或顯示。
4. 設定一次後，每次到該網域附近時會自動連線。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/faq:wlan_auth"""

TANETROAMING_ANSWER = """`TANetRoaming` 是可用於校內或校外漫遊的 Web-based 認證 Wi-Fi。

**校內使用**
1. 在 Wi-Fi 清單中選擇 `TANetRoaming`。
2. 連上後打開瀏覽器，系統會帶出登入頁面。
3. 輸入無線網路帳號與密碼後即可上網。

**外校漫遊**
1. 若人在其他有加入漫遊的大學，也可以搜尋 `TANetRoaming`。
2. 使用清大帳號登入時，帳號格式請使用 `s學號@wlan.nthu.edu.tw`。
3. 若連線品質不穩，請先確認所在學校該區域的無線訊號狀況。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/faq:wlan_auth"""

EXTERNAL_EDUROAM_QUALITY_ANSWER = """在外校使用 `eduroam` 很慢或不穩時，通常要分成「帳號格式」和「現場無線環境」兩邊確認。

**先確認帳號格式**
1. 在外校使用 `eduroam` 漫遊時，帳號請輸入 `s學號@wlan.nthu.edu.tw`。
2. 密碼是清大校園無線區域網路帳號的密碼，不一定是校務資訊系統密碼。

**再確認現場環境**
1. 若能登入但速度很慢，通常比較可能與所在學校當下的基地台訊號、使用人數或現場網路狀況有關。
2. 可先換到訊號較強的位置，或重新連線 `eduroam` 測試。
3. 若在同一地點持續很慢，請記錄所在學校、建築物、樓層、時間、裝置系統與錯誤畫面。

**尋求幫助**
若確認帳號格式正確但仍無法使用，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在學校、位置、連線 SSID、帳號格式、裝置系統與截圖，以便協助判斷是否為帳號或漫遊認證問題。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/faq:wlan_useless"""

EDUROAM_ANSWER = """**WiFi 登入（設定一次即可）（802.1X + PEAP）**
eduroam 對應的 Wi-Fi 名稱是 `eduroam`。第一次使用時，請依以下步驟設定：

1. 在裝置的 Wi-Fi 設定中，選擇 `eduroam`。
2. 接著會要求輸入帳號密碼，請輸入無線網路帳號（格式為 `s學號`）與申請時設定的密碼。
3. 完成設定後，裝置會自動儲存憑證，之後每次連線會自動認證，不需要重新輸入帳號密碼。

**尋求幫助**
若仍登入失敗，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供裝置系統、所在位置、連線的 SSID、帳號格式、錯誤訊息，並附上 Wi-Fi 設定、認證畫面或錯誤畫面截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/faq:wlan_roaming"""

NTHUPEAP_ANSWER = EDUROAM_ANSWER.replace("eduroam 對應的 Wi-Fi 名稱是 `eduroam`", "nthupeap 對應的 Wi-Fi 名稱是 `nthupeap`").replace("選擇 `eduroam`", "選擇 `nthupeap`")

EDUROAM_FAILURE_ANSWER = """eduroam 登入失敗時，請先以「帳號密碼」、「原本設定」和「現場訊號」三個方向檢查。

**先確認帳號密碼**
1. 若是在清大校內使用 `eduroam` 或 `nthupeap`，帳號請輸入無線網路帳號，格式為 `s學號`。
2. 若是在外校使用 `eduroam` 漫遊，帳號請輸入 `s學號@wlan.nthu.edu.tw`。
3. 密碼是申請無線網路帳號時設定的密碼，不一定是校務資訊系統密碼。

**重新設定連線**
1. 在裝置 Wi-Fi 設定中刪除或忘記原本儲存的 `eduroam` 設定。
2. 重新選擇 `eduroam` 後，再輸入正確帳號與密碼。
3. 若仍失敗，可重新開機後再試一次，避免裝置沿用舊的認證設定。

**確認使用環境**
1. 若在清大校內，請確認所在位置有校園無線網路涵蓋，且訊號不要太弱。
2. 若在外校，請確認該校有提供 `eduroam` 漫遊服務。
3. 若錯誤訊息與帳號密碼無關，請保留錯誤畫面截圖。

**尋求幫助**
若仍登入失敗，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供裝置系統、所在位置、連線的 SSID、帳號格式、錯誤訊息，並附上 Wi-Fi 設定、認證畫面或錯誤畫面截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_useless
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/faq:wlan_roaming"""

NTHU_CC_ANSWER = """`nthu-cc` 是清大校內無線網路的 Web-based 認證 Wi-Fi。使用方式如下：

1. 在校內 Wi-Fi 清單中選擇 `nthu-cc`。
2. 連上後打開瀏覽器，系統通常會自動跳出登入頁面。
3. 在登入頁面輸入無線網路帳號與密碼後即可上網。
4. 如果登入頁面沒有自動跳出，請手動開啟 Chrome、Firefox、Edge 或 Safari，連到任一網頁，通常就會導出認證頁面。
5. 若仍無法使用，可先關閉 Wi-Fi 後重新開啟，再重新連線一次。

**尋求幫助**
若仍無法登入或上網，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、裝置系統、連線的 SSID、錯誤訊息，並附上 Wi-Fi 設定或登入畫面截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_auth
https://net.nthu.edu.tw/netsys/faq:wlan_useless"""


ROUTER_TROUBLESHOOTING_ANSWER = """如果已照分享器設定步驟做了還是不行，請先依序檢查下面幾點：

1. 確認分享器的 WAN 端接在宿舍網路孔，不是接在 LAN 端。
2. 確認分享器 WAN 連線類型是「固定 IP」，不是自動取得 IP（DHCP）。
3. 確認已填入申請宿網後取得的 IP、子網路遮罩、閘道與 DNS 等 TCP/IP 設定資訊。
4. 檢查 IP、子網路遮罩、閘道與 DNS 是否有打錯，尤其是數字、點號與欄位位置。
5. 如果分享器設定後仍無法上網，請先用電腦直接接宿舍網路線，並填入同一組宿網 IP 設定測試。
6. 若電腦直接接線可以上網，問題多半在分享器 WAN 設定；若電腦直接接線也不能上網，可能是宿網 IP 設定、網路線、網路孔或宿網服務狀態問題。

**尋求幫助**
若仍無法解決，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、分享器型號、WAN 設定畫面、IP 設定資訊、電腦直接接線測試結果與錯誤畫面截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_network_config2
https://net.nthu.edu.tw/netsys/faq:domitory_network_config"""

WIRELESS_TROUBLESHOOTING_ANSWER = """無線網路無法連線時，可先依「認證問題」、「IP 問題」與「其他問題」三個方向檢查。

**認證問題**
1. **網頁認證沒有跳出：**如果使用 `nthu-cc` 或 `TANetRoaming`，請先確認裝置已連上正確 SSID。若沒有自動跳出認證頁面，請手動開啟常用瀏覽器，例如 Chrome、Firefox 或 Edge，連到任一網頁，通常就會導出認證頁面。
2. **瀏覽器憑證或頁面導出異常：**若使用 Firefox 進行網頁認證時無法正確導出認證首頁，可參考 Firefox 無線網路網頁認證說明。
3. **閒置過久無法認證：**若等待太久才認證，建議先關閉裝置的 Wi-Fi 功能再重新啟動，重新連線後再嘗試認證。
4. **802.1X 連線未設定完成：**如果使用 `nthupeap` 或 `eduroam`，請確認裝置已依作業系統平台完成相關設定，且校園無線網路帳號皆使用小寫英文字母。
5. **帳號或密碼問題：**請查詢校園無線區域網路帳號密碼狀態，確認帳號可正常使用且密碼正確。若仍無效，建議清除原本的 `nthupeap` 或 `eduroam` 設定、重新開機後再重新設定。

**IP 問題**
1. **使用了固定 IP：**若裝置的無線網路設定使用靜態固定 IP，可能無法取得無線網路自動分配的 IP，也可能無法導出認證頁面。請將無線網路設定改成「自動取得 IP 位址」。
2. **無法取得 IP 位址：**若裝置分配不到可用 IP，可能是該區域同時連線的裝置較多。可向該連線區域的單位網管諮詢或反應。
3. **認證後仍無法連線：**若不是上述情況，但認證後仍無法上網，可嘗試關閉裝置 Wi-Fi 再重新啟動，讓裝置重新取得 IP 位址。

**其他問題**
1. **所在區域可能沒有涵蓋或訊號微弱：**連線前可先確認該區域是否屬於校園無線網路涵蓋範圍，也可向該區域單位網管諮詢或反應。
2. **裝置無線功能異常：**若裝置不具備無線上網功能，或無線網路卡無法正常運作，建議請專業資訊人員協助測試與確認。
3. **仍無法判定原因：**請盡量提供截圖與詳細資訊後回報問題，可使用計通中心通報網、無線網路服務信箱 `wlan@cc.nthu.edu.tw`，或校內分機 `31235`。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_useless"""


WIRELESS_CREDENTIAL_ANSWER = """清大無線網路帳號與密碼不是校務資訊系統那組，而是另外申請的「校園無線區域網路帳號」。

**帳號與密碼怎麼來**
1. 先到校務資訊系統中的「計通中心相關服務」裡的「網路系統組線上服務」。
2. 選擇「無線區域網路帳號」進行申請。
3. 申請時會設定無線網路密碼，之後連 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam` 時使用這組帳密。

若是在清大校內使用 `nthupeap` 或 `eduroam`，帳號格式通常為 `s學號`；若是在外校使用 `eduroam` 漫遊，帳號格式為 `s學號@wlan.nthu.edu.tw`。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/faq:wlan_auth"""

WIRELESS_PASSWORD_EFFECTIVE_ANSWER = """無線網路帳號密碼重新設定後，通常約 10 分鐘內生效。

如果你剛改完密碼但還連不上，可以先等約 10 分鐘，再把裝置中原本儲存的 `nthupeap` 或 `eduroam` 設定刪除後重新連線。

詳細可參考：
https://net.nthu.edu.tw/netsys/wireless:application
https://net.nthu.edu.tw/netsys/faq:wlan_auth"""

EN_WIRELESS_PASSWORD_EFFECTIVE_ANSWER = """After resetting the campus wireless LAN account password, it usually becomes effective in about 10 minutes.

If you just changed the password but still cannot connect, wait about 10 minutes, then forget the saved `nthupeap` or `eduroam` Wi-Fi profile on your device and reconnect.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth"""

WIRELESS_PASSWORD_ANSWER = """清大學生的無線網路帳號與密碼不是校務資訊系統的帳密，而是另外申請的「校園無線區域網路帳號」。

**忘記無線網路密碼時有下面三種方式處理：**

**可登入校務資訊系統**
1. 登入校務資訊系統並從清大校內 IP 連線。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 選擇「無線區域網路帳號」，重新設定密碼。
4. 完成後約 10 分鐘內生效。

**無法登入校務資訊系統，但還記得原無線密碼**
1. 從清大校內 IP 連線。
2. 開啟無線區域網路帳號密碼重設頁面：
https://www.wlan.nthu.edu.tw/~wlan/cgi-bin/NM/MyUserPWmod.pl
在頁面中設定新密碼。
3. 完成後約 10 分鐘內生效。

**書面申請**
1. 下載並填寫「教職員工生校園無線區域網路帳號申請單」。
2. 至計通中心二樓服務台辦理。
3. 書面申請送件後約三個工作天。"""

VPN_ANSWER = """校外連線至學校校內網路，需透過學校提供的 VPN 服務。請先申請並啟用校園無線區域網路帳號的 VPN 功能，再依作業系統設定 VPN 連線。

**VPN 帳號申請與啟用**
1. 登入校務資訊系統。
2. 在左方選單中點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 點選「登入網路系統組線上服務」。
4. 選擇「無線區域網路帳號」。
5. 填入資訊，並在「VPN 設定」欄勾選「啟用」。
6. 完成後帳號約 10 分鐘內生效。

**VPN 連線設定**
1. 下載 Ivanti Secure Access Client 或 Pulse Secure。下載網址不同資料夾代表不同版本，請擇一下載。下載網址：
https://ndrive.niar.org.tw/navigate/a/#/s/894C6D3B91C94C3EB0D0B4237BC47B426BL
載點登入密碼為 `nchc`。
2. 安裝 Ivanti Secure Access Client 或 Pulse Secure。
3. 啟動安裝好的 VPN 軟體。
4. 點選「+」，「名稱」及「伺服器」欄皆填入 `nthu.twaren.net`，再點選「連線」。
5. 輸入校園無線區域網路帳號及密碼進行驗證，帳號格式為 `s學號@wlan.nthu.edu.tw`。
6. 驗證成功後，即可連上校內網路。

**尋求幫助**
若申請或連線時遇到問題，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供裝置系統、VPN 軟體名稱、帳號格式、錯誤訊息與相關截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/sslvpn:info
https://net.nthu.edu.tw/netsys/sslvpn:sslvpn_setup
https://net.nthu.edu.tw/netsys/wireless:application:ccxp"""

DORM_CONFIG_ANSWER = """若你已申請宿舍網路後，申請完後的每日 10 時與 16 時進行系統處理完畢後即可使用宿網，宿網 IP 設定的操作說明如下：

若您是使用分享器，請接著詢問客服「分享器要怎麼連宿舍網路？」；若為電腦裝置直接連接網路線，請接著參考：

1. 確認裝置已連接至宿舍網路線。
2. 進入裝置的網路設定，選擇乙太網路。
3. 在乙太網路的設定中，點選編輯 IP 指派。
4. 編輯 IP 設定視窗中，將自動（DHCP）更改為「手動」、IPv4 設定為開啟。
5. 將申請宿網後所給定的 TCP/IP 設定填入後按儲存。
6. IP 設定完成，試看看能不能上網吧！

**尋求幫助**
若設定後仍無法使用，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、裝置系統、是否有設定 IP、錯誤訊息，並附上相關 IP 設定及網路狀況等截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_network_config"""

DORM_USELESS_ANSWER = """宿網前幾天正常、最近突然連不到時，建議先從「狀態查詢」和「交叉測試」兩個方向確認。

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

#### 尋求幫助
若仍無法判斷，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍與房號、裝置系統、是否有設定 IP、查詢狀態結果、交叉測試結果、錯誤訊息，並附上 IP 設定與網路狀況截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""

DORM_CONTEXT_CORRECTION_ANSWER = """了解，你問的是宿網突然無法連線。若前幾天正常、今天突然不能用，可以先照下面方向檢查：

1. 查詢 IP / 網路狀態，確認是否被封鎖。
2. 查詢禁用狀態，確認是否因違反宿網使用規定被停用。
3. 查詢用戶設備埠狀態，確認是否可能是宿網設備或房間網路孔異常。
4. 做交叉測試：換網路線、換電腦，或到其他已開通宿網的寢室測試。測試時記得使用對應網路孔的 IP 設定。

**尋求幫助**
若仍無法判斷，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、裝置系統、是否有設定 IP、查詢狀態結果、交叉測試結果、錯誤訊息與截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""

DORM_STATUS_CHECK_ANSWER = """宿網狀態可以先從宿舍網路服務頁與宿網 FAQ 說明進去查。你要查的是上一則提到的「IP / 網路狀態、禁用狀態、用戶設備埠狀態」。

**要去哪裡看**
1. 先開啟宿舍網路服務頁：
https://net.nthu.edu.tw/netsys/dormnet/
2. 在頁面中找到宿網相關查詢或管理系統入口。
3. 依序查看 IP / 網路狀態、禁用狀態，以及用戶設備埠狀態。
4. 如果狀態顯示被封鎖、禁用或設備埠異常，請依頁面顯示原因處理，或把查詢結果截圖提供給宿網信箱協助判斷。

**如果你只是想看操作說明**
可以先看宿網無法連線 FAQ，裡面會說明要先做狀態查詢與交叉測試。

**尋求幫助**
若查完仍看不懂結果，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍與房號、查詢狀態截圖、裝置系統、IP 設定畫面與錯誤訊息。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""


DORM_IP_LOOKUP_ANSWER = """如果你忘記自己的宿網 IP，或想查目前申請到的宿網 IP/TCP/IP 設定資訊，可以到宿網申請狀態查詢頁查看。

**查詢方式**
1. 開啟宿網申請狀態查詢頁：
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl
2. 使用先前在校務資訊系統「網路系統組線上服務」設定的學生宿舍網路帳號密碼登入。
3. 帳號類型或電子郵件欄位請選擇「宿網帳號（DormNet Account）」。
4. 登入後查看目前宿舍網路申請狀態，以及申請到的 IP/TCP/IP 設定資訊。

如果查到 IP 後不知道怎麼填，可以接著問「宿網 IP 要怎麼設定」。

**尋求幫助**
若無法登入或查不到資料，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍與房號、帳號類型選擇畫面、錯誤訊息與截圖，以便技術人員協助。

詳細可參考：
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless"""

DORM_IP_STATUS_ANSWER = """如果要查宿網 IP 狀態、IP 是否被禁用，或宿網突然異常，可以先依宿網無法連線 FAQ 的方向檢查。

**先查狀態**
1. 查詢 IP / 網路狀態，確認目前 IP 是否正常、是否被封鎖或有異常紀錄。
2. 查詢禁用狀態，確認是否因宿網使用規範或異常流量被暫停使用。
3. 查詢用戶設備埠狀態，確認房間網路孔或宿網設備是否可能異常。
4. 若狀態頁有顯示原因，先依頁面提示處理；看不懂時請截圖提供給宿網信箱協助判斷。

**如果忘記自己的 IP**
可以到宿網申請狀態查詢頁查看目前申請到的 IP/TCP/IP 設定資訊：
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl

登入時請使用先前在校務資訊系統「網路系統組線上服務」設定的學生宿舍網路帳號密碼，帳號類型選擇「宿網帳號（DormNet Account）」。

**尋求幫助**
若查詢後仍無法判斷，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍與房號、查詢狀態截圖、裝置系統、IP 設定畫面與錯誤訊息。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl"""


DORM_USELESS_FOLLOWUP_ANSWER = """如果已照前面的宿網排查步驟做了還是不行，下一步請把檢查結果整理出來，這樣比較能判斷是帳號狀態、IP 設定、網路孔、網路線或設備問題。

**請先確認這幾項結果**
1. IP / 網路狀態查詢結果是否顯示被封鎖、禁用或異常。
2. 用戶設備埠狀態查詢結果是否正常。
3. 電腦直接接宿舍網路孔時，是否已填入該網路孔對應的 IP、子網路遮罩、閘道與 DNS。
4. 換一條網路線後是否仍無法連線。
5. 用同一台電腦到其他可用宿網的房間測試是否能上網。
6. 請室友或其他同學用他的電腦接你的房間網路孔，是否也無法上網。

**怎麼判斷**
1. 如果你的電腦到其他正常網路孔也不能上網，較可能是電腦設定、網路線或 IP 設定問題。
2. 如果別人的電腦接你的房間網路孔也不能上網，較可能是房間網路孔、線路或宿網設備狀態問題。
3. 如果狀態查詢顯示被封鎖或禁用，請依狀態頁原因處理，或聯絡宿網確認。

**尋求幫助**
若仍無法判斷，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、裝置系統、IP 設定畫面、狀態查詢結果、交叉測試結果、錯誤訊息與網路狀況截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""

DORM_ACCOUNT_PASSWORD_ANSWER = """宿網帳號密碼是在校務資訊系統的「網路系統組線上服務」裡設定的「學生宿舍網路帳號」密碼。

**這組帳密用途**
1. 用來登入宿舍網路申請頁面或宿網管理系統。
2. 完成宿網帳號密碼設定後，只代表帳號已建立，還不等於宿網服務已完成申請。
3. 還需要接續進入宿舍網路申請頁面，填寫宿舍資料並取得 IP 設定資訊。

如果你是忘記宿網密碼，請回到校務資訊系統的「學生宿舍網路帳號」頁面重新設定；若是已能登入但不能上網，請改查宿網狀態、IP 設定或網路孔狀態。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/dormnet/"""


DORM_AVAILABILITY_ANSWER = """清大學生宿舍有提供宿舍網路服務，但通常需要住宿生完成宿網申請後才能使用。

**使用前需要確認**
1. 你目前是住宿生，且住宿資料已完成登記。
2. 已在校務資訊系統設定「學生宿舍網路帳號」。
3. 已到宿舍網路申請頁面填寫宿舍資料，取得宿網 IP 設定資訊。
4. 系統每日 10 時與 16 時進行處理，處理完畢後才能依取得的 IP 設定使用宿網。

若你想問的是某間宿舍或某個房間突然不能上網，請描述宿舍名稱、房號、使用電腦或分享器，以及錯誤情況，系統會改用宿網故障排除方向協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/dormnet/
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply"""


DORM_PORT_REPAIR_ANSWER = """如果懷疑是宿舍房間網路孔壞掉，建議直接向宿網信箱報修，並把狀況說明清楚，附圖會更有利於技術人員判斷。

**報修前可先確認**
1. 同一台電腦與同一條網路線接到其他可用宿網的房間，是否可以上網。
2. 室友或其他同學的電腦接到你的房間網路孔，是否也無法上網。
3. 已確認 IP 設定使用的是該網路孔對應的宿網 IP 資訊。
4. 用戶設備埠狀態查詢是否顯示異常。

**報修時請提供**
1. 宿舍名稱與房號。
2. 疑似故障的網路孔位置。
3. 目前狀況，例如完全無法連線、燈號異常、時好時壞等。
4. 交叉測試結果。
5. IP 設定畫面、錯誤訊息、網路孔或網路線連接狀況截圖，附圖佳。

**宿網聯絡資訊**
請向宿網信箱 dorms@cc.nthu.edu.tw 說明疑似網路孔壞掉的情況並提出報修，技術人員會依你提供的資訊協助確認。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/dormnet/"""

ROUTER_ANSWER = """分享器連接宿舍網路時，請把分享器的 WAN 端接到宿舍網路孔，並將 WAN 連線類型設定為固定 IP。設定方式如下：

1. 確認分享器連接好，WAN 端請連接至宿舍網路孔。
2. 用電腦或手機連接分享器網路。此時可能會顯示無網際網路連線，這是正常的。
3. 開啟瀏覽器，進入分享器管理介面，常見網址可能是 `192.168.1.1` 或 `192.168.0.1`，實際以分享器說明為準。
4. 在 WAN、外部網路或網際網路設定中，連線類型選擇「固定 IP」。
5. 輸入申請宿舍網路後取得的 IP、子網路遮罩、閘道與 DNS 等 TCP/IP 設定資訊。
6. 儲存後測試電腦、手機等設備是否可以透過分享器上網。

**尋求幫助**
若設定後仍有問題，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、分享器型號、WAN 設定畫面、IP 設定資訊與錯誤畫面截圖。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_network_config2"""

DORM_APPLY_ANSWER = """宿網申請共分成下面兩大步：

**申請宿舍網路帳號**

1. 先登入「校務資訊系統」。
2. 進入系統後，於左方選單點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 接著在右方點選「登入網路系統組線上服務」。
4. 在畫面下方點選「學生宿舍網路帳號」並確認目前申請裝置有連上學校網路，需在學校網域內申請。
5. 進入申請頁面後，請先閱讀「校園網路使用規範」與「學生宿舍網路使用規範」等規範。
6. 在畫面中間設定您的宿網密碼，並點選底部的「同意」按鈕。
7. 宿網帳號密碼設定完成後，目前僅完成帳號申請，請接續[申請宿舍網路](https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/A1.pl)。

**申請宿舍網路**

8. 進入宿舍網路申請頁面後，輸入剛剛在校務資訊系統設定的帳號密碼，電子郵件選取宿網帳號（DormNet Account）。
9. 接下來請填寫宿舍的相關資訊，申請型態選擇「登錄」。
10. 提出申請後會出現您申請到的宿網 IP 設定資訊，此資料會寄到您上一步填寫的 Email，請記得該 IP 的設定資訊，之後連接宿網會需要用到。
11. 您已完成宿網申請，提出申請後，每日 10 時與 16 時進行系統處理完畢後即可使用。

若對如何設定宿網 IP 有疑問的話，可繼續詢問「要怎麼設定宿舍網路」。

**尋求幫助**
若申請過程中遇到問題，或已申請後仍無法連線，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、裝置系統、是否有設定 IP、錯誤訊息，並附上相關 IP 設定及網路狀況等截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply"""


DORM_ACCOUNT_INCOMPLETE_ANSWER = """「帳號未申請完成」通常是指您只做到前半段，還沒有完成整個宿舍網路申請流程。

宿舍網路申請分成兩件事：

**1. 申請學生宿舍網路帳號**
這一步是在校務資訊系統裡設定宿網帳號密碼。完成後，只代表您有宿網帳號可以登入後續申請頁面。

**2. 申請宿舍網路服務**
接著還要到宿舍網路申請頁面登入，填寫宿舍資料，申請型態選擇「登錄」，送出後取得宿網 IP 設定資訊。

如果只完成第 1 步，尚未完成第 2 步，就可能會被理解成帳號或宿網申請尚未完成。完成宿網服務申請後，系統會在每日 10 時與 16 時進行處理，處理完畢後才可使用宿網。

若您不確定現在做到哪一步，可以繼續問「宿舍網路怎麼申請？」或「要怎麼設定宿舍網路」。

**尋求幫助**
若申請過程中遇到問題，或已申請後仍無法連線，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、裝置系統、是否有設定 IP、錯誤訊息，並附上相關 IP 設定及網路狀況等截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/faq:domitory_net_apply"""




DORM_TRANSFER_CAUSE_ANSWER = """有可能跟換宿有關。換宿後，宿舍房間、網路孔與宿網 IP 設定可能會跟原房間的資料不同，因此通常需要確認住宿組資料已更新，並在宿網申請系統把宿舍資料更新成新的房間。

**先確認換宿資料**
1. 先確認住宿組已完成換宿資料登記。
2. 若住宿資料尚未同步，宿網申請系統可能無法正確對應到新房間。

**到宿網系統更新資料**
1. 登入「校務資訊系統」。
2. 進入「計通中心相關服務」裡的「網路系統組線上服務」。
3. 點選「學生宿舍網路帳號」，確認宿網帳號可使用。
4. 進入宿舍網路申請頁面：
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/A1.pl
5. 用宿網帳號登入後，填寫新房間的宿舍資料。
6. 申請型態請選擇「更新」。
7. 送出後保留新的宿網 IP 設定資訊，系統每日 10 時與 16 時處理，處理完畢後再依新的 IP 設定連線。

如果是換宿後才連不上，建議優先檢查是否已在宿網系統更新新房間資料，以及電腦或分享器是否仍沿用舊房間的 IP 設定。

**尋求幫助**
若更新後仍無法連線，請向宿網信箱 dorms@cc.nthu.edu.tw 提供原宿舍、新宿舍房號、是否已在宿網系統選「更新」、目前 IP 設定畫面、錯誤訊息與網路狀況截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/faq:domitory_net_apply
https://net.nthu.edu.tw/netsys/dormnet/"""


DORM_TRANSFER_APPLY_ANSWER = """換宿後的宿網申請流程與一般申請相同，請依下列步驟辦理：

**1. 確認換宿已完成**：先確認住宿組已完成換宿資料登記。

**2. 申請宿舍網路**：

**a. 申請宿舍網路帳號**
1. 先登入「校務資訊系統」。
2. 進入系統後，於左方選單點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 接著在右方點選「登入網路系統組線上服務」。
4. 在畫面下方點選「學生宿舍網路帳號」，並確認目前申請裝置有連上學校網路，需在學校網域內申請。
5. 進入申請頁面後，請先閱讀「校園網路使用規範」與「學生宿舍網路使用規範」等規範。
6. 在畫面中間設定您的宿網密碼，並點選底部的「同意」按鈕。
7. 宿網帳號密碼設定完成後，目前僅完成帳號申請，請接續申請宿舍網路：
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/A1.pl

**b. 申請宿舍網路**
8. 進入宿舍網路申請頁面後，輸入剛剛在校務資訊系統設定的帳號密碼，電子郵件選取宿網帳號（DormNet Account）。
9. 接下來請填寫宿舍的相關資訊，申請型態選擇「更新」。
10. 提出申請後會出現您申請到的宿網 IP 設定資訊，此資料會寄到您上一步填寫的 Email，請記得該 IP 設定資訊，之後連接宿網會需要用到。
11. 您已完成宿網申請。提出申請後，每日 10 時與 16 時進行系統處理，處理完畢後即可使用。

若對如何設定宿網 IP 有疑問，可繼續詢問「要怎麼設定宿舍網路」。

**尋求幫助**
若申請過程中遇到問題，或已申請後仍無法連線，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、裝置系統、是否有設定 IP、錯誤訊息，並附上相關 IP 設定及網路狀況等截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/faq:domitory_net_apply
https://net.nthu.edu.tw/netsys/dormnet/"""


MAIL_SIZE_SOURCES = [
    source("faq:mail_quota_size [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:mail_quota_size", "單封郵件總大小上限為 50MB，附件編碼後整封郵件會變大。"),
]

MAIL_QUOTA_SOURCES = [
    source("faq:mail_quota_size [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:mail_quota_size", "清大信箱容量與單封郵件大小說明。"),
    source("faq:mail_quota_exceed [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:mail_quota_exceed", "信箱容量超過限制時的處理說明。"),
]

GAPP_APPLICATION_ANSWER = """**G Suite for Education（gapp）信箱申請步驟：**
1. 登入「校務資訊系統」。
2. 點選左方選單「計通中心相關服務」裡的「網路系統組線上服務」。
3. 點選「Google Apps 帳號申請」。
4. 確認閱讀完必要資料，並填完個人資料與電子郵件地址後確認申請。

詳細可參考：
https://net.nthu.edu.tw/netsys/gapp#帳號申請流程"""

STUDENT_EMAIL_APPLICATION_ANSWER = """**校內學生電子郵件信箱申請步驟：**

1. 登入「校務資訊系統」。
2. 點選左方選單「計通中心相關服務」裡的「網路系統組線上服務」。
3. 在右方畫面點選「登入網路系統組線上服務」。
4. 點選「學生信箱申請」，並確認申請時連線來源為校內 IP（140.114.0.0/16 或 120.127.160~191.*）。
5. 閱讀並同意相關使用規範後，系統會自動產生學生信箱帳號（格式為 `s學號@m入學年度.nthu.edu.tw`，如 `s112345678@m112.nthu.edu.tw`）。確認密碼輸入完成且帳號申請成功後，新建信箱約可在 10 分鐘內生效。

詳細可參考：
https://net.nthu.edu.tw/netsys/mail:application_student:new_std"""

STUDENT_EMAIL_FORMAT_ANSWER = """清大學生信箱格式為：

`s學號@m入學年度.nthu.edu.tw`

例如學號為 `112345678`，入學年度為 `112`，信箱格式會是：

`s112345678@m112.nthu.edu.tw`

詳細可參考：
https://net.nthu.edu.tw/netsys/mail:application_student:new_std"""

EMAIL_APPLICATION_ANSWER = """清大有兩個常見信箱：校內學生電子郵件信箱與 G Suite for Education（gapp）信箱。

**校內學生電子郵件信箱申請步驟：**
1. 登入「校務資訊系統」。
2. 點選左方選單「計通中心相關服務」裡的「網路系統組線上服務」。
3. 在右方畫面點選「登入網路系統組線上服務」。
4. 點選「學生信箱申請」，並確認申請時連線來源為校內 IP（140.114.0.0/16 或 120.127.160~191.*）。
5. 閱讀並同意相關使用規範後，系統會自動產生學生信箱帳號（格式為 `s學號@m入學年度.nthu.edu.tw`，如 `s112345678@m112.nthu.edu.tw`）。確認密碼輸入完成且帳號申請成功後，新建信箱約可在 10 分鐘內生效。

**G Suite for Education（gapp）信箱申請步驟：**
1. 登入「校務資訊系統」。
2. 點選左方選單「計通中心相關服務」裡的「網路系統組線上服務」。
3. 點選「Google Apps 帳號申請」。
4. 確認閱讀完必要資料，並填完個人資料與電子郵件地址後確認申請。

詳細可參考：
https://net.nthu.edu.tw/netsys/mail:application_student:new_std
https://net.nthu.edu.tw/netsys/gapp#帳號申請流程"""

OFFCAMPUS_SMTP_ANSWER = """在校外使用清大信箱寄信時，中心的一般 SMTP 伺服器不直接接受校外 IP 寄信，以避免成為垃圾信跳板。

1. 先連線清大 TWAREN SSL VPN，再使用中心 SMTP 伺服器寄信。
2. 改用目前網路 ISP 業者提供的 SMTP 伺服器。
3. 使用中心提供的 SMTP AUTH 驗證寄信服務。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:mail_smtp_auth_outside_campus"""

VACATION_REPLY_ANSWER = """可以在新版 Roundcube Webmail 設定假期自動回覆。

1. 登入新版 Roundcube Webmail，點選上方「設定」。
2. 點選左方「轉信與假期自動回信」。
3. 勾選「假期自動回應」與「在伺服器上保留郵件備份」。
4. 填寫假期自動回信的主旨與內容。
5. 點選「儲存」。

假期結束後，請回到同一頁取消勾選「假期自動回應」並儲存。

詳細可參考：https://net.nthu.edu.tw/netsys/mail:config:vacation"""

GMAIL_APP_ANSWER = """可以使用 Gmail App，以加密 IMAP 收信並以 SMTP AUTH 寄信。

1. 在 Gmail App 選擇「新增帳戶」。
2. 選擇「個人（IMAP/POP）」並輸入清大電子郵件地址。
3. 選擇「個人（IMAP）」，填入內送伺服器設定。
4. 接著填入外寄 SMTP 伺服器設定並完成新增帳戶。

內送設定使用短帳號、信箱網域對應的伺服器、連接埠 993 與 SSL/TLS；外寄伺服器為 `smtpauth.net.nthu.edu.tw`，使用包含網域的完整帳號、連接埠 25 與 STARTSSL。

詳細可參考：https://net.nthu.edu.tw/netsys/mail:gmail_app"""

WEBMAIL_AUTO_LOGOUT_ANSWER = """Webmail 會基於帳號安全與 session 管理自動登出；長時間沒有操作、瀏覽器 session 到期或連線環境改變時，都可能需要重新登入。

請重新登入 Webmail；撰寫較長郵件時建議先儲存草稿，避免 session 到期後內容遺失。若剛登入不久便反覆被登出，可清除該網站的 Cookie、重新開啟瀏覽器，並確認網路連線是否穩定。

若問題持續，請記錄登出時間、使用的瀏覽器與畫面訊息，以便管理人員確認。

詳細可參考：https://net.nthu.edu.tw/netsys/faq:webmail:autologout"""

WEBMAIL_USAGE_ANSWER = """清大 Webmail 可從以下網址登入使用：
https://webmail.nthu.edu.tw/

詳細可參考：https://net.nthu.edu.tw/netsys/mail:webmail"""

MAIL_BLACK_WHITE_LIST_ANSWER = """可以透過隔離垃圾信通知信或郵件記錄器設定個人黑名單與白名單。

**郵件記錄器設定方式**
1. 登入 https://mr.net.nthu.edu.tw/ 。
2. 點選右上方使用者名稱，再選擇「編輯」。
3. 進入「黑白名單」頁籤，新增寄件者完整地址或網域。
4. 白名單寄件者會被視為正常信；黑名單寄件者會被視為垃圾信。

建議匯出個人黑白名單自行備份。

詳細可參考：https://net.nthu.edu.tw/netsys/faq:mail_white_black_address"""


MAILBOX_FULL_ANSWER = """收到 `mailbox full` 表示信箱容量已滿，新的郵件可能無法正常收進來。

**處理方式**
1. 登入自己信箱所對應的 Webmail。
2. 刪除不需要的舊郵件，優先整理含有大型附件的郵件。
3. 檢查寄件備份、草稿與垃圾桶，刪除不需要的內容。
4. 清空垃圾桶，讓已刪除郵件確實釋放信箱容量。
5. 完成後再次測試是否能正常收信。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:mail_quota_size
https://net.nthu.edu.tw/netsys/faq:mail_quota_exceed"""


MAIL_LARGE_MESSAGE_ANSWER = """`552 5.3.4` 常見原因之一，是附件編碼後使整封郵件超過寄信大小限制。

清大郵件資料記載，單封郵件總大小上限為 50MB。附件加入郵件後還會經過編碼，整封郵件可能增加約 1.3 至 4 倍，因此原始附件未滿 50MB，寄出時仍可能超過限制。

**處理方式**
1. 將附件縮小或分成數封郵件寄送。
2. 較大的檔案可改用檔案分享方式，再將下載連結放在郵件內。
3. 若縮小附件後仍被退回，請查看完整退信內容；`552 5.3.4` 可能與郵件大小有關，但仍應以退信中的完整說明為準。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:mail_quota_size"""


CAMPUS_QUALITY_SUFFIXES = ("館", "院", "樓", "中心", "大樓")
CAMPUS_QUALITY_TERMS = (
    "網路很差", "網路差", "品質", "訊號差", "不穩", "很慢", "慢", "很卡", "卡",
    "斷線", "一直斷", "怪怪", "超爛", "很爛", "爛", "連不到", "連不上", "無法連線", "不能連",
    "不能用", "無法上網", "轉圈圈", "一直轉", "跑不動", "掛了", "死掉", "沒反應",
    "網頁開不了", "網頁打不開", "網頁都開不了", "沒有網際網路", "沒網際網路",
    "網頁載不出來", "載不出來", "載不動", "動不了", "開不出來", "上不了網",
    "訊號滿格", "搜不到", "找不到wifi", "找不到wi-fi",
)


def extract_campus_place(question: str) -> str:
    compact = question.strip().replace(" ", "")
    for alias, canonical in (
        ("總圖", "圖書館"),
        ("圖書館", "圖書館"),
        ("水木生活中心", "水木生活中心"),
        ("水木", "水木生活中心"),
        ("小吃部", "小吃部"),
    ):
        if alias in compact:
            return canonical
    zong_match = re.search(r"綜(?:合)?([一二三四五六七八九十0-9]+)(?:館)?", compact)
    if zong_match:
        return f"綜合{zong_match.group(1)}館"

    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9]{1,12}(?:館|院|樓|中心|大樓))", question)
    if not match:
        return "該地點"
    place = re.sub(r"^.*[在於]", "", match.group(1))
    place = re.sub(r"^(那|請問|想問|問一下|欸)", "", place)
    return place or match.group(1)


def is_wireless_quality_question(question: str) -> bool:
    normalized = normalize_text(question)
    has_place = any(suffix in normalized for suffix in CAMPUS_QUALITY_SUFFIXES) or any(
        term in normalized for term in ("總圖", "水木", "小吃部", "梅園", "紅吱吱")
    )
    has_quality = any(term in normalized for term in CAMPUS_QUALITY_TERMS)
    has_network = any(term in normalized for term in (
        "網路", "wifi", "wi-fi", "無線", "訊號", "連線", "eduroam", "nthupeap",
        "nthucc", "nthu-cc", "tanetroaming", "網頁", "有連上", "已連線",
    ))
    campus_context = has_place or any(term in normalized for term in ("校園網路", "學校網路", "校園wifi", "學校wifi"))
    return campus_context and has_quality and has_network


def build_wireless_quality_answer(question: str) -> str:
    place = extract_campus_place(question)
    return f"""如果你在{place}連不到網路，或最近覺得網路很差，可以先從 Wi-Fi 名稱、訊號環境、認證與 IP 狀態這幾個方向檢查。

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
若同一位置持續訊號差或完全無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、樓層、連線的 SSID、裝置系統、發生時間、錯誤訊息與網路狀況截圖，以便技術人員協助確認。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_useless
https://net.nthu.edu.tw/netsys/faq:wlan_range"""


def english_place_name(place: str | None) -> str | None:
    place_names = {
        "圖書館": "the library",
        "總圖": "the library",
        "風雲樓": "Fengyun Building",
        "水木生活中心": "Shui Mu Life Center",
        "水木": "Shui Mu Life Center",
        "台達館": "Delta Building",
        "台積館": "TSMC Building",
        "物理館": "Physics Building",
        "資電館": "EECS Building",
    }
    return place_names.get(place or "", place)


def chinese_place_name(place: str | None) -> str | None:
    place_names = {
        "the library": "圖書館",
        "library": "圖書館",
        "Fengyun Building": "風雲樓",
        "Feng Yun Building": "風雲樓",
        "Shui Mu Life Center": "水木生活中心",
        "Shui Mu": "水木生活中心",
        "Delta Building": "台達館",
        "TSMC Building": "台積館",
        "Physics Building": "物理館",
        "EECS Building": "資電館",
        "that NTHU location": "該地點",
        "that location": "該地點",
    }
    return place_names.get(place or "", place)


def build_english_wireless_quality_answer(place: str | None = None) -> str:
    prefix = "For slow or unstable NTHU campus Wi-Fi"
    place = english_place_name(place)
    if place == "該地點":
        place = "that NTHU location"
    if place:
        prefix = f"If NTHU campus Wi-Fi at {place} is slow, unstable, or cannot connect"
    return f"""{prefix}, first check the Wi-Fi name, signal environment, authentication status, and IP settings.

**Check the connection source**
1. Make sure you are connected to the correct NTHU Wi-Fi. On campus, you can use `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam`.
2. If you are connected to a similar-looking, weak, or non-NTHU Wi-Fi name, the connection may be unstable.

**Check signal and location**
1. If you are far from an access point, behind walls, or in a crowded area, the signal quality may drop.
2. Move to a hallway, public area, or a spot with stronger signal and test again.

**Check authentication and IP status**
1. For `nthu-cc` or `TANetRoaming`, open a browser and confirm whether you need to log in again.
2. For `nthupeap` or `eduroam`, forget the saved Wi-Fi setting and reconnect.
3. Wi-Fi IP settings should normally use automatic IP assignment, not a fixed IP.

**Get help**
If the same location remains slow or unusable, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, time, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless
https://net.nthu.edu.tw/netsys/en:faq:wlan_range"""


def build_campus_building_range_answer(question: str) -> tuple[str, list[dict[str, Any]]] | None:
    normalized = normalize_text(question)
    if not any(term in normalized for term in ("有網路嗎", "有wifi嗎", "有wi-fi嗎", "有無線網路嗎", "有沒有網路", "有沒有wifi", "是否有網路", "是否有wifi")):
        return None

    location = extract_location_slot(question)
    if not location:
        return None
    response = build_coverage_response(location)
    return response["answer"], response["sources"]


def location_answer(question: str) -> tuple[str, list[dict[str, Any]]] | None:
    normalized = normalize_text(question)

    if any(term in normalized for term in ("哪裡有網路", "哪裡有wifi", "哪裡有wi-fi", "哪裡有無線", "哪些地方有網路", "哪些地方有wifi", "學校其他地方有網路", "其他學校地方是否有網路")):
        answer = """清大校園無線網路主要分成「公共區」和「部分系所單位」兩類。

**公共區無線網路**
可使用的公共區包含部分餐廳、遠距教室、風雲樓、水木生活中心、宿舍公共區、醫輔大樓，以及部分戶外公共區。

**部分系所單位**
有些系所單位也有自行建置並介接計通中心認證主機的無線網路，例如人社院等。實際可用範圍會依現場訊號和單位管理情況而定。

**到現場怎麼確認**
如果想確認某個地點能不能用，可以到現場搜尋 `nthu-cc`、`nthupeap`、`TANetRoaming` 或 `eduroam`。若查不到或訊號很弱，再向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統、錯誤訊息與截圖，請技術人員協助確認。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy"""
        return answer, WLAN_RANGE_SOURCES
    location = extract_location_slot(question)
    if location and is_network_availability_request(question):
        response = build_coverage_response(location)
        return response["answer"], response["sources"]


    if "紅吱吱" in normalized:
        if "小吃部" in normalized or "水木" in normalized:
            sections = []
            summary = []
            if "小吃部" in normalized:
                summary.append("小吃部有提供校園無線網路")
                sections.append("**小吃部**\n小吃部與小吃部戶外廣場有列在清大公共區無線網路範圍中。")
            if "水木" in normalized:
                summary.append("水木生活中心有提供校園無線網路")
                sections.append("**水木生活中心**\n水木生活中心列在公共區無線網路範圍中。")
            summary.append("紅吱吱牛排等校外餐廳不屬於清大校園無線網路涵蓋範圍")
            sections.append("**紅吱吱牛排**\n紅吱吱牛排等校外餐廳不屬於清大校園無線網路涵蓋範圍，因此沒有清大校園無線網路。")
            answer = "；".join(summary) + "。\n\n" + "\n\n".join(sections) + "\n\n詳細可參考：\nhttps://net.nthu.edu.tw/netsys/faq:wlan_range\nhttps://net.nthu.edu.tw/netsys/wireless:easy"
        else:
            answer = """紅吱吱牛排等校外餐廳不屬於清大校園無線網路涵蓋範圍，因此沒有清大校園無線網路。

如果是在紅吱吱附近想使用網路，需以店家或一般行動網路為主；清大校園無線網路無法保證涵蓋校外餐廳。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy"""
        return answer, WLAN_RANGE_SOURCES

    places = []
    if "人社院" in normalized:
        places.append("人社院")
    if "小吃部" in normalized:
        places.append("小吃部")
    if "水木" in normalized:
        places.append("水木生活中心")
    if "風雲樓" in normalized:
        places.append("風雲樓")
    if "醫輔" in normalized or "醫輔大樓" in normalized:
        places.append("醫輔大樓")
    if "梅園" in normalized:
        places.append("梅園")
    if not places:
        return None

    sections = []
    for place in places:
        if place == "人社院":
            sections.append("**人社院**\n人社院列在有提供無線區域網路服務並介接計通中心認證主機服務的系所單位中，可先嘗試使用校園無線網路。")
        if place == "小吃部":
            sections.append("**小吃部**\n小吃部與小吃部戶外廣場列在公共區無線網路範圍中，可先嘗試使用校園無線網路。")
        if place == "水木生活中心":
            sections.append("**水木生活中心**\n水木生活中心列在公共區無線網路範圍中，可先嘗試使用校園無線網路。")
        if place == "風雲樓":
            sections.append("**風雲樓**\n風雲樓列在公共區無線網路範圍中，可先嘗試使用校園無線網路。")
        if place == "醫輔大樓":
            sections.append("**醫輔大樓**\n醫輔大樓列在公共區無線網路範圍中，可先嘗試使用校園無線網路。")
        if place == "梅園":
            sections.append("**梅園**\n目前資料無法確認梅園列在校園無線網路涵蓋範圍中。若在梅園現場搜尋不到 `nthu-cc`、`nthupeap`、`TANetRoaming` 或 `eduroam`，通常表示該處可能沒有清大 Wi-Fi 覆蓋或訊號太弱，建議移到鄰近有涵蓋的室內或公共區再測試。")
    answer = "\n\n".join(sections) + "\n\n若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。\n\n詳細可參考：\nhttps://net.nthu.edu.tw/netsys/faq:wlan_range\nhttps://net.nthu.edu.tw/netsys/wireless:easy"
    return answer, WLAN_RANGE_SOURCES

SEGMENTED_DORM_CONTEXT_ANSWER = """了解，你是在宿舍這邊。請再補充你遇到的是哪一種宿網狀況，我才能給你比較準確的排查步驟。

可以直接描述成：
1. 宿網突然不能連、變慢或斷線。
2. 分享器設定後不能上網。
3. 宿網 IP 不知道怎麼填。
4. 網路孔疑似故障。

如果是宿網突然變慢或不能連，也可以補充宿舍房號、是否使用分享器、從什麼時候開始、錯誤訊息或網路狀態截圖。"""

EN_SEGMENTED_DORM_CONTEXT_ANSWER = """Got it. You are in the dormitory. Please add the DormNet issue so I can give the right troubleshooting steps.

You can describe it as:
1. DormNet suddenly stopped working, became slow, or keeps disconnecting.
2. A router is connected but cannot access the Internet.
3. You are not sure how to enter the DormNet IP settings.
4. The room network wall port may be broken.

If DormNet suddenly became slow or unavailable, please include your dorm and room number, whether you use a router, when it started, and screenshots of errors or network status if possible."""

SEGMENTED_CAMPUS_LOCATION_ANSWER = """了解，你目前在清大校內。請再補充你遇到的是哪一種網路狀況，我才能判斷要用校園 Wi-Fi、宿網、VPN 或其他服務的資料回答。

可以直接描述成：
1. 連線的 Wi-Fi 名稱，例如 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam`。
2. 問題狀況，例如很慢、連不上、登入頁跳不出來或登入失敗。
3. 位置細節，例如建築物、樓層或教室附近。"""

EN_SEGMENTED_CAMPUS_LOCATION_ANSWER = """Got it. You are at an NTHU campus location. Please add the network detail so I can answer with the right NTHU network service.

You can provide:
1. The Wi-Fi name, such as `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam`.
2. The issue, such as slow connection, disconnecting, login page not appearing, or login failure.
3. More location detail, such as building, floor, or nearby classroom.
"""

SEGMENTED_SCHOOL_CONTEXT_ANSWER = """了解，你是在學校遇到網路問題。請再補充你使用的是哪一種服務，這樣我才能給你正確步驟。

可以告訴我：
1. 你是在宿舍用宿網，還是在校園內用 Wi-Fi。
2. 如果是 Wi-Fi，連的是 `nthu-cc`、`TANetRoaming`、`nthupeap` 還是 `eduroam`。
3. 目前狀況是很慢、連不上、登入頁跳不出來，還是帳號密碼錯誤。"""

EN_SEGMENTED_SCHOOL_CONTEXT_ANSWER = """Got it. You are at NTHU. Please add which network service you are using so I can give the right steps.

You can tell me:
1. Whether you are using DormNet in a dormitory or campus Wi-Fi on campus.
2. If it is Wi-Fi, the SSID, such as `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam`.
3. The issue, such as slow connection, cannot connect, login page not appearing, or login failure.
"""

SEGMENTED_ROUTER_CONTEXT_ANSWER = """了解，你是在宿舍使用分享器。若是要讓分享器連宿網，通常需要把分享器 WAN 端接到宿舍網路孔，並將 WAN 連線類型設定為固定 IP。

如果你還沒設定，可以接著問「分享器要怎麼連宿舍網路？」；如果已經填固定 IP 但仍不能上網，請補充分享器型號、WAN 設定截圖，以及電腦直接接宿舍網路孔是否可以上網。"""

SEGMENTED_OFFCAMPUS_ROAMING_ANSWER = """你目前在交大或其他外校時，如果是想使用清大的無線網路帳號上網，通常會是校外漫遊情境。

請在現場 Wi-Fi 清單找 `eduroam` 或 `TANetRoaming`。若使用 `eduroam`，帳號格式請輸入 `s學號@wlan.nthu.edu.tw`，密碼是清大校園無線區域網路帳號的密碼。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_roaming
https://net.nthu.edu.tw/netsys/faq:wlan_auth"""

EXTERNAL_OR_AMBIGUOUS_NETWORK_ANSWER = """我需要先確認一下地點，因為這個客服主要回答清大網路系統組相關問題。

你說的「台大」是指台灣大學校園網路，還是想問清大校內某個地點的網路狀況？

如果是清大校內，請再提供：
1. 具體地點，例如物理館、台達館、資電館，以及樓層或教室位置。
2. 連線的 Wi-Fi 名稱，例如 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam`。
3. 問題狀況，例如很慢、斷線、連不上、登入頁面跳不出來。

如果是台大校園網路，建議詢問台大校內網路服務單位，因為清大網路系統組無法確認台大無線網路設備與涵蓋狀態。"""

EN_EXTERNAL_OR_AMBIGUOUS_NETWORK_ANSWER = """I need to confirm the location first, because this service mainly answers questions about the NTHU Network Systems Division.

When you say “NTU”, do you mean National Taiwan University’s campus network, or are you asking about a location on the NTHU campus?

If you mean an NTHU campus location, please provide:
1. The exact location, such as Physics Building, Delta Building, TSMC Building, plus the floor or classroom area.
2. The Wi-Fi name, such as `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam`.
3. The issue, such as slow connection, disconnecting, cannot connect, or login page not appearing.

If you mean the NTU campus network, please contact NTU’s network service unit, because the NTHU Network Systems Division cannot verify NTU wireless equipment or coverage."""


def get_clarification_answer(question: str) -> tuple[str, list[dict[str, Any]]] | None:
    normalized = normalize_text(question)
    explicit_external_school = any(term in normalized for term in (
        "台大", "臺大", "台灣大學", "臺灣大學", "nationaltaiwanuniversity", "ntu"
    ))
    network_issue = any(term in normalized for term in (
        "網路很差", "網路差", "wifi很慢", "wi-fi很慢", "網路很慢", "訊號差", "不穩", "斷線", "連不上", "無法連線", "networkisnotworking", "schoolnetworkisnotworking"
    ))
    if explicit_external_school and network_issue:
        return EXTERNAL_OR_AMBIGUOUS_NETWORK_ANSWER, []
    if "換宿" in normalized and any(term in question for term in DORM_BUILDING_TERMS):
        return DORM_TRANSFER_CAUSE_ANSWER, DORM_APPLY_SOURCES
    if any(term in question for term in DORM_BUILDING_TERMS) and not any(term in normalized for term in (
        "宿網", "宿舍網路", "網路", "wifi", "wi-fi", "無線", "連", "申請", "設定",
        "壞", "故障", "慢", "卡", "爛", "不穩", "斷線", "沒網路", "沒有網路",
        "無法上網", "不能上網", "不能用", "異常", "怪怪", "品質",
    )):
        return SEGMENTED_DORM_CONTEXT_ANSWER, []
    if any(term in normalized for term in ("moveddorm", "moveddorms", "movingdorm", "movingdorms", "changedorm", "changedorms", "newdorm", "newroom", "movedfrom", "couldthatberelated", "couldmovingdormsberelated")) and any(term in normalized for term in EN_DORM_BUILDING_TERMS + ("dormnet", "dormitorynetwork", "dormnetwork")):
        return EN_DORM_TRANSFER_CAUSE_ANSWER, EN_DORM_APPLY_SOURCES
    if any(term in normalized for term in EN_DORM_BUILDING_TERMS) and not any(term in normalized for term in ("internet", "network", "wifi", "wi-fi", "wireless", "connect", "vpn", "email", "apply", "set", "slow", "unstable", "disconnect", "bad", "notwork")):
        return EN_SEGMENTED_DORM_CONTEXT_ANSWER, []
    if any(term in normalized for term in ("我在宿舍", "人在宿舍", "我住宿舍", "住在宿舍")) and not any(term in normalized for term in ("網路", "wifi", "wi-fi", "無線", "連", "申請", "設定", "壞", "故障", "分享器")):
        return SEGMENTED_DORM_CONTEXT_ANSWER, []
    if any(term in normalized for term in ("iliveinthedorm", "iliveinadorm", "liveinthedorm", "liveinadorm", "iaminthedorm", "iminthedorm", "iaminthedormitory", "iminthedormitory")) and not any(term in normalized for term in ("network", "wifi", "wi-fi", "wireless", "connect", "vpn")):
        return EN_SEGMENTED_DORM_CONTEXT_ANSWER, []
    if ("忘記" in normalized and "密碼" in normalized and "網路" in normalized) or any(term in normalized for term in ("忘記網路密碼", "忘記學校網路密碼")):
        return WIRELESS_PASSWORD_ANSWER, WIRELESS_SOURCES
    if any(term in normalized for term in ("iamatanotheruniversity", "imatanotheruniversity", "atanotheruniversity")) and not has_network_failure_intent(question):
        return EN_EDUROAM_ROAMING_ACCOUNT_ANSWER, EN_EDUROAM_ROAMING_SOURCES
    if any(term in normalized for term in ("我宿舍有接分享器", "宿舍有接分享器", "宿舍接分享器", "我有接分享器", "我有用分享器", "有用分享器")):
        return SEGMENTED_ROUTER_CONTEXT_ANSWER, DORM_ROUTER_SOURCES[:1]
    if any(term in normalized for term in ("我現在在交大", "人在交大", "我在交大", "我現在在陽明交大", "人在陽明交大")):
        return SEGMENTED_OFFCAMPUS_ROAMING_ANSWER, WIRELESS_SOURCES[:2]
    if any(term in normalized for term in ("我要在家連學校內網", "在家連學校內網", "校外連學校內網", "在家連校內網路", "校外連校內網路")):
        return VPN_ANSWER, VPN_SOURCES
    if any(term in normalized for term in ("我在學校", "人在學校", "我在校內", "人在校內")) and not any(term in normalized for term in ("網路", "wifi", "wi-fi", "無線", "連", "vpn", "信箱")):
        return SEGMENTED_SCHOOL_CONTEXT_ANSWER, []
    if any(term in normalized for term in ("iamatnthu", "imatnthu", "iamonnthucampus", "imonnthucampus")) and not any(term in normalized for term in ("network", "wifi", "wi-fi", "wireless", "connect", "vpn", "email")):
        return EN_SEGMENTED_SCHOOL_CONTEXT_ANSWER, []
    if any(term in normalized for term in ("我人在台達館", "人在台達館", "我在台達館", "我人在台積館", "人在台積館", "我在台積館", "我人在物理館", "人在物理館", "我在物理館", "我人在資電館", "人在資電館", "我在資電館", "我人在風雲樓", "人在風雲樓", "我在風雲樓", "我人在圖書館", "人在圖書館", "我在圖書館", "我人在水木", "人在水木", "我在水木")) and not any(term in normalized for term in ("網路", "wifi", "wi-fi", "無線", "連", "vpn")):
        return SEGMENTED_CAMPUS_LOCATION_ANSWER, []
    if any(term in normalized for term in ("iaminthephysicsbuilding", "iminthephysicsbuilding", "iamindeltabuilding", "imindeltabuilding", "iaminthelibrary", "iminthelibrary", "iaminfengyunbuilding", "iminfengyunbuilding", "iamatfengyunbuilding", "imatfengyunbuilding")) and not any(term in normalized for term in ("network", "wifi", "wi-fi", "wireless", "connect", "vpn")):
        return EN_SEGMENTED_CAMPUS_LOCATION_ANSWER, []
    if normalized in {"我網路不能用", "網路不能用", "我不能上網", "無法上網", "連不上網路"}:
        return AMBIGUOUS_NETWORK_ANSWER, []
    if normalized in {"theschoolnetworkisnotworking", "schoolnetworkisnotworking", "networkisnotworking", "icannotconnecttotheschoolnetwork"}:
        return EN_AMBIGUOUS_NETWORK_ANSWER, []
    return None


EN_WIRELESS_SOURCES = [
    source("en:faq#wireless_network [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq#wireless_network", "Wireless network authentication and roaming information."),
    source("en:wireless:application [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application", "Campus wireless LAN account application."),
    source("en:faq [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq", "NTHU Network Systems Division FAQ."),
]

EN_WIRELESS_APPLICATION_SOURCES = [
    source("en:wireless:application [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application", "Campus wireless LAN account application."),
    source("en:wireless:application:ccxp [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp", "Wireless application via Academic Information System."),
]

EN_EDUROAM_ROAMING_SOURCES = [
    source("en:faq:wlan_roaming [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming", "Wireless roaming and eduroam account format."),
    source("en:faq:wlan_auth [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_auth", "Wireless authentication settings."),
]

EN_DORM_APPLY_SOURCES = [
    source("en:faq:domitory_net_ua_apply [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_ua_apply", "Dormitory network account application."),
    source("en:faq:domitory_net_apply [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_apply", "Dormitory network service application."),
    source("en:dormnet [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:dormnet/", "Dormitory network service."),
]

EN_DORM_ROUTER_SOURCES = [
    source("en:faq:domitory_network_config2 [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config2", "Router setup for dormitory network."),
    source("en:faq:domitory_network_config [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config", "Dormitory network TCP/IP settings."),
]

EN_WLAN_RANGE_SOURCES = [
    source("en:faq:wlan_range [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_range", "Wireless LAN coverage."),
    source("en:wireless:easy [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:easy", "Wireless network easy guide."),
]

EN_EDUROAM_FAILURE_SOURCES = [
    source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting."),
    source("en:faq:wlan_auth [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_auth", "Wireless authentication settings."),
    source("en:faq:wlan_roaming [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming", "Wireless roaming and eduroam account format."),
]

EN_EMAIL_SOURCES = [
    source("en:mail:application_student:new_std [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std", "Student email application."),
    source("en:gapp [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:gapp#account_application_process", "Google Apps / gapp account application."),
]

EN_MAIL_QUOTA_SOURCES = [
    source("en:faq:mail_quota_size [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:mail_quota_size", "Mailbox quota and message size."),
    source("en:faq:mail_quota_exceed [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:mail_quota_exceed", "Mailbox quota exceeded."),
]

EN_VPN_SOURCES = [
    source("en:sslvpn:info [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:sslvpn:info", "SSL VPN service information."),
    source("en:sslvpn:sslvpn_setup [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:sslvpn:sslvpn_setup", "SSL VPN setup."),
    source("en:wireless:application:ccxp [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp", "Wireless account and VPN activation."),
]

EN_NTHU_CC_ANSWER = """`nthu-cc` is NTHU campus Wi-Fi that uses browser login.

**How to use it**
1. In the Wi-Fi list, select `nthu-cc`.
2. After connecting, open a browser.
3. The login page should appear automatically.
4. Enter your campus wireless LAN account and password to access the Internet.

If the login page does not appear, reconnect to `nthu-cc` and open a normal website in your browser to trigger the login page.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_NTHU_CC_LOGIN_PAGE_ANSWER = """If the `nthu-cc` login page does not appear, check these items first.

**Browser login check**
1. Make sure you are connected to `nthu-cc`.
2. Open a common browser such as Chrome, Edge, Firefox, or Safari.
3. Visit a normal website to trigger the wireless login page.
4. If the device was idle for a long time, turn Wi-Fi off and on, reconnect to `nthu-cc`, and try again.

**Network setting check**
1. Make sure the Wi-Fi IP setting is automatic IP assignment, not a fixed IP.
2. If the browser still cannot redirect to the login page, try another browser or forget `nthu-cc` and reconnect.

**Get help**
If it still fails, contact wlan@cc.nthu.edu.tw with your location, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth"""

EN_VPN_ACCOUNT_FORMAT_ANSWER = """For the NTHU VPN, log in with your campus wireless LAN account and password.

**Account format**
`sStudentID@wlan.nthu.edu.tw`

Use the password you set for the campus wireless LAN account. It is not necessarily the same as your Academic Information System password.

For details:
https://net.nthu.edu.tw/netsys/en:sslvpn:info
https://net.nthu.edu.tw/netsys/en:sslvpn:sslvpn_setup
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp"""


EN_VPN_PASSWORD_ANSWER = """For the NTHU VPN client, enter the password of your campus wireless LAN account. This is the password you set on the Network Systems Division service page in the Academic Information System.

**Where to set or check it**
1. Log in to the Academic Information System.
2. Open “Computer and Communication Center Services” and then “Network Systems Division Online Services”.
3. Select “Wireless LAN Account”.
4. Apply for or reset the campus wireless LAN account password there.
5. The new password usually becomes effective in about 10 minutes.

When logging in to the VPN client, use `sStudentID@wlan.nthu.edu.tw` as the account format and enter that wireless LAN password.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp
https://net.nthu.edu.tw/netsys/en:sslvpn:info"""


EN_VPN_DOWNLOAD_VERSION_ANSWER = """The folders such as `22.7R2.4`, `22.7R2.6`, `22.7R2.8`, `9.1R14`, and `9.1R17` are VPN client software version numbers.

**What to do next**
1. Open one of the newer version folders first.
2. Inside the folder, choose the installer for your operating system, such as Windows or macOS.
3. If the NTHU instruction page does not specify a version, it is usually reasonable to choose a newer version. If you are unsure, send your OS and a screenshot of the folders to the wireless network service mailbox for confirmation.
4. After installation, return to the VPN client setup. Use `nthu.twaren.net` as the server and log in with `sStudentID@wlan.nthu.edu.tw`.

**Get help**
If you are not sure which version to download, contact wlan@cc.nthu.edu.tw with your operating system and screenshots of the folder or file names.

For details:
https://net.nthu.edu.tw/netsys/en:sslvpn:info
https://net.nthu.edu.tw/netsys/en:sslvpn:sslvpn_setup"""

EN_WIRELESS_USAGE_ANSWER = """NTHU campus Wi-Fi can be used in two common ways.

**Browser login**
Connect to `nthu-cc` or `TANetRoaming`. After connecting, open a browser; the login page should appear. Enter your campus wireless LAN account and password to use the network.

**WiFi login (set once only)**
Connect to `nthupeap` or `eduroam`. The first time, enter your campus wireless LAN account and password in the device Wi-Fi settings. After the setting is saved, the device can authenticate automatically next time.

**Off-campus roaming**
At another university that supports roaming, look for `TANetRoaming` or `eduroam`. For off-campus roaming, use the account format `sStudentID@wlan.nthu.edu.tw`.

For details:
https://net.nthu.edu.tw/netsys/en:faq#wireless_network
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:faq"""

EN_WIRELESS_APPLICATION_ANSWER = """**Apply for a campus wireless LAN account**

1. Log in to the Academic Information System.
2. In the left menu, open the Computer and Communication Center related services, then enter the Network Systems Division online service.
3. Select “Wireless LAN Account” and complete the application.
4. Set your wireless LAN account password. VPN is not required for normal Wi-Fi use and can be enabled only if you need it.

This application page must be accessed from an NTHU campus IP address.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp"""

EN_VPN_OPTIONAL_ANSWER = """No. If you only want to use campus Wi-Fi, you do not have to enable VPN.

VPN is only needed when you want to connect to NTHU internal network resources from off campus. You can enable it only if you need it.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp
https://net.nthu.edu.tw/netsys/en:sslvpn:info"""

EN_NTHU_CC_SWITCH_WIFI_ANSWER = """If the `nthu-cc` login page does not appear, you can try these Wi-Fi options instead:

1. `TANetRoaming`: it also uses browser login. Connect to it, then open a browser and see whether the login page appears.
2. `nthupeap` or `eduroam`: enter your campus wireless LAN account and password in the device Wi-Fi settings. After setup, the device can log in automatically next time.

For quick troubleshooting, try `TANetRoaming` first. If you prefer not to open a browser each time, set up `nthupeap` or `eduroam`.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_GAPP_EFFECTIVE_ANSWER = """The available gapp instructions do not clearly state exactly how long it takes for a G Suite for Education (gapp) account to become available after application.

After submitting the application, wait a while and then try signing in. If it still does not work, contact the responsible staff through the gapp page or Network Systems Division service, and include your application time, account information, and screenshots so they can check the status.

For details:
https://net.nthu.edu.tw/netsys/en:gapp#account_application_process"""

EN_EXTERNAL_EDUROAM_FAILURE_ANSWER = """If `eduroam` login keeps failing at another university, check the username format, password, and local roaming service.

**Check the account and password**
1. Use `sStudentID@wlan.nthu.edu.tw` as the username.
2. The password is your NTHU campus wireless LAN account password, not necessarily your Academic Information System password.
3. If you just changed the password, wait about 10 minutes and try again.

**Reset the saved Wi-Fi setting**
1. Forget or delete the saved `eduroam` profile on your device.
2. Select `eduroam` again and enter the full username and password.
3. Make sure the letters in the account are lowercase.

**Check the local environment**
1. Confirm that the other university provides `eduroam` roaming at that location.
2. If the signal is weak or login keeps failing in the same spot, move to an area with stronger signal and test again.

**Get help**
If it still fails, contact wlan@cc.nthu.edu.tw with the university, SSID, device OS, username format, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless"""

EN_DORM_REPAIR_EMAIL_INFO_ANSWER = """When emailing the DormNet mailbox for repair, include the information below so the technicians can judge whether the issue is the wall port, cabling, IP settings, or DormNet equipment.

**Email contact:** send the message to `dorms@cc.nthu.edu.tw`.

**Include these details**
1. Dormitory name and room number.
2. The location of the suspected broken network wall port.
3. What happens now, such as no connection, intermittent connection, or abnormal port/cable lights.
4. Cross-test results, such as whether your computer and cable work in another room, and whether another computer also fails on your wall port.
5. Whether you confirmed the IP settings match the DormNet IP assigned to that wall port.
6. Screenshots of IP settings, error messages, network status, and photos of the wall port or cable if possible.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/en:dormnet/"""

EN_WIRELESS_APPLICATION_PAGE_ANSWER = """If the wireless LAN application page will not open, check the following items first.

**Check whether you are using an NTHU campus IP**
1. The application page must be accessed from an NTHU campus IP address.
2. If you are off campus, connect to the NTHU VPN first and then try opening the page again.

**If you are already on campus but still cannot open it**
1. Log in to the Academic Information System again.
2. In the left menu, open the Computer and Communication Center related services, then enter the Network Systems Division online service.
3. Click the Network Systems Division online service login link again.
4. If you see `Cannot get checksum or expired`, the link has likely expired after about 2 minutes. Generate a new link and try again.
5. If you see `IP mismatch`, the current source IP differs from the one used when logging in. Reconnect using a stable network and log in again.

**Get help**
If it still fails, contact wlan@cc.nthu.edu.tw with your device OS, location, current network source, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp"""

EN_AMBIGUOUS_NETWORK_ANSWER = """I need a little more information to identify the correct NTHU network service.

Please provide:
1. The service: DormNet, campus Wi-Fi, VPN, email, or another NTHU network service.
2. Your location: for example dormitory and room number, Physics Building, Delta Building, or Library.
3. The connection type or SSID: network cable, `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam`.
4. The exact issue: cannot connect, slow connection, login failed, login page does not appear, IP setting problem, or any error message.

You can write it like: “I am at [location], using [SSID/service], and I see [error/problem].”"""

EN_WIRELESS_QUALITY_ANSWER = """For slow or unstable NTHU campus Wi-Fi, first check the connection source, signal environment, and authentication/IP status.

**Check the connection source**
1. Make sure you are connected to the correct NTHU Wi-Fi. On campus, you can use `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam`.
2. If you are connected to a similar-looking or non-NTHU Wi-Fi name, the connection may be unstable.

**Check signal and location**
1. If you are far from an access point, behind walls, or in a crowded area, the signal quality may drop.
2. Move to a hallway, public area, or a spot with stronger signal and test again.

**Check authentication and IP status**
1. For `nthu-cc` or `TANetRoaming`, open a browser and confirm whether you need to log in again.
2. For `nthupeap` or `eduroam`, forget the saved Wi-Fi setting and reconnect.
3. Wi-Fi IP settings should normally use automatic IP assignment, not a fixed IP.

**Get help**
If the same location remains slow or unusable, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, time, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless
https://net.nthu.edu.tw/netsys/en:faq:wlan_range"""

EN_CAFETERIA_WIFI_ANSWER = """**Cafeteria**
The cafeteria and the outdoor cafeteria plaza are listed in the public-area wireless network coverage. You can try using NTHU campus Wi-Fi there.

If the signal is weak or the connection fails, contact wlan@cc.nthu.edu.tw with the exact location, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_FENGYUN_WIFI_ANSWER = """**Fengyun Building**
Fengyun Building is listed in the public-area wireless network coverage. You can try using NTHU campus Wi-Fi there.

If the signal is weak or the connection fails, contact wlan@cc.nthu.edu.tw with the exact location, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_MEI_GARDEN_WIFI_ANSWER = """**Mei Garden**
The current coverage data does not confirm Mei Garden as part of the campus wireless network coverage. If you cannot see `nthu-cc`, `nthupeap`, `TANetRoaming`, or `eduroam` there, the area may not have NTHU Wi-Fi coverage or the signal may be too weak. Move to a nearby covered indoor or public area and test again.

If you still need confirmation, contact wlan@cc.nthu.edu.tw with the exact location, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_DORM_PORT_REPAIR_ANSWER = """If you suspect the dormitory room network wall port is broken, contact the DormNet mailbox and describe the situation clearly. Screenshots or photos are helpful for troubleshooting and repair.

**Before reporting**
1. Test the same computer and network cable in another room where DormNet works.
2. Ask a roommate or another student to connect their computer to your room's network wall port.
3. Make sure the IP settings match the DormNet IP information assigned to that wall port.
4. Check whether the user port status query shows anything abnormal.

**When reporting, provide**
1. Dormitory name and room number.
2. The location of the suspected broken network wall port.
3. What happens now, such as no connection, abnormal indicator lights, intermittent connection, or other symptoms.
4. Cross-test results.
5. Screenshots of IP settings, error messages, network status, and photos of the wall port or cable if possible.

**DormNet contact**
Please email dorms@cc.nthu.edu.tw and explain that the network wall port may be broken and needs repair.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/en:dormnet/"""

EN_DORM_TRANSFER_CAUSE_ANSWER = """Yes, it could be related to the dorm change. After moving dormitories, your room, wall port, and DormNet IP settings may be different from the previous room, so you should confirm that the Housing Division record has been updated and then update your dormitory information in the DormNet application system.

**Check the dorm change record first**
1. Confirm that the Housing Division has completed the dorm change record.
2. If the housing data has not been synchronized yet, the DormNet system may not match your new room correctly.

**Update your DormNet information**
1. Log in to the Academic Information System.
2. Enter the Network Systems Division online service from the Computer and Communication Center related services menu.
3. Select “Student Dormitory Network Account” and confirm that your DormNet account is usable.
4. Open the DormNet application page:
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/A1.pl
5. Log in with your DormNet account and fill in the new dormitory room information.
6. Choose “Update” as the application type.
7. Submit the update and keep the new IP settings. The system processes requests daily at 10:00 and 16:00.

If you moved from Xin Zhai to Ru Zhai and the issue started after moving, first check whether your DormNet application has been updated to the Ru Zhai room and whether your computer or router is still using the old room's IP settings.

**Get help**
If it still does not work after updating, contact dorms@cc.nthu.edu.tw with your old dorm, new dorm and room number, whether you selected “Update” in the DormNet system, current IP settings, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_apply
https://net.nthu.edu.tw/netsys/en:dormnet/"""

EN_WIRELESS_CREDENTIAL_ANSWER = """No. Your NTHU WiFi password is not the same as your Academic Information System password.

The WiFi account and password belong to the campus wireless LAN account, which must be applied for separately.

**Where it comes from**
1. Log in to the Academic Information System.
2. Enter the Network Systems Division online service from the Computer and Communication Center related services menu.
3. Select “Wireless LAN Account” and set your wireless LAN password.

For `nthupeap` or `eduroam` on campus, the account format is usually `sStudentID`. For `eduroam` roaming at another university, use `sStudentID@wlan.nthu.edu.tw`.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth"""

EN_WIRELESS_PASSWORD_RESET_ANSWER = """Your NTHU campus wireless LAN account and password are not the same thing as the Academic Information System account and password. The wireless password is set separately when you apply for the campus wireless LAN account.

**If you can log in to the Academic Information System**
1. Connect from an NTHU campus IP address.
2. Log in to the Academic Information System.
3. In the left menu, open the Computer and Communication Center related services, then enter the Network Systems Division online service.
4. Select “Wireless LAN Account” and reset the wireless LAN password.
5. The new password usually becomes effective in about 10 minutes.

**If you cannot log in to the Academic Information System but still remember the old wireless password**
1. Connect from an NTHU campus IP address.
2. Use the wireless LAN account password reset page:
https://www.wlan.nthu.edu.tw/~wlan/cgi-bin/NM/MyUserPWmod.pl
3. The new password usually becomes effective in about 10 minutes.

**Written application**
1. Download and fill out the campus wireless LAN account application form.
2. Submit it to the Computer and Communication Center second-floor service desk.
3. Written applications usually take about three working days.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth"""

EN_TANETROAMING_ANSWER = """`TANetRoaming` uses browser login.

**How to use it**
1. Select `TANetRoaming` from the Wi-Fi list.
2. Open a browser after connecting. The login page should appear.
3. Enter your campus wireless LAN account and password to use the network.

**When using it at another university**
If the other university provides `TANetRoaming`, use your NTHU roaming account format: `sStudentID@wlan.nthu.edu.tw`.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth"""

EN_EDUROAM_ROAMING_ACCOUNT_ANSWER = """For `eduroam` at another university, use your NTHU campus wireless LAN account in this format:

`sStudentID@wlan.nthu.edu.tw`

Use the password you set for your NTHU campus wireless LAN account. This password is not necessarily the same as your Academic Information System password.

After you select `eduroam` in the Wi-Fi list, enter the full account format above and save the setting.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth"""

EN_NTHUPEAP_ANSWER = """**WiFi login (set once only)**
**(802.1X + PEAP)**
Use the Wi-Fi name `nthupeap`. The first time you connect, follow these steps:

1. In your device Wi-Fi settings, select `nthupeap`.
2. When it asks for a username and password, enter your campus wireless LAN account. For on-campus `nthupeap`, the account format is `sStudentID`.
3. Enter the password you set when applying for the campus wireless LAN account.
4. After the setting is saved, the device should authenticate automatically next time.

For help, contact wlan@cc.nthu.edu.tw with your device OS, location, SSID, account format, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth
https://net.nthu.edu.tw/netsys/en:wireless:application"""

EN_EDUROAM_USAGE_ANSWER = """**WiFi login (set once only)**
**(802.1X + PEAP)**
Use the Wi-Fi name `eduroam`. The first time you connect, follow these steps:

1. In your device Wi-Fi settings, select `eduroam`.
2. If you are on the NTHU campus, enter your campus wireless LAN account in the format `sStudentID`.
3. If you are using eduroam at another university, enter `sStudentID@wlan.nthu.edu.tw`.
4. Enter the password you set when applying for the campus wireless LAN account.
5. After the setting is saved, the device should authenticate automatically next time.

For help, contact wlan@cc.nthu.edu.tw with your device OS, location, SSID, account format, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming"""

EN_EDUROAM_ON_CAMPUS_ANSWER = """**WiFi login (set once only)**
**(802.1X + PEAP)**
On the NTHU campus, use the Wi-Fi name `eduroam`. The first time you connect, follow these steps:

1. In your device Wi-Fi settings, select `eduroam`.
2. When it asks for a username and password, enter your campus wireless LAN account. On the NTHU campus, the account format is `sStudentID`.
3. Enter the password you set when applying for the campus wireless LAN account.
4. After the setting is saved, the device should authenticate automatically next time.

Do not add the `@wlan.nthu.edu.tw` suffix on campus; that suffix is only for roaming.

For help, contact wlan@cc.nthu.edu.tw with your device OS, location, SSID, account format, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth
https://net.nthu.edu.tw/netsys/en:wireless:application"""

EN_EDUROAM_FAILURE_ANSWER = """If `eduroam` login fails, check the account format, saved Wi-Fi setting, and local signal first.

**Check the account format**
1. On the NTHU campus, use your campus wireless LAN account in the format `sStudentID`.
2. At another university, use `sStudentID@wlan.nthu.edu.tw`.
3. The password is the one you set for the campus wireless LAN account, not necessarily your Academic Information System password.

**Reset the saved Wi-Fi setting**
1. Forget or delete the saved `eduroam` Wi-Fi profile on your device.
2. Select `eduroam` again and enter the correct account and password.
3. If it still fails, restart the device and try again.

**Check the environment**
1. On the NTHU campus, make sure the location has campus Wi-Fi coverage and the signal is not too weak.
2. At another university, make sure that university provides `eduroam` roaming service.
3. Keep a screenshot of any error message.

For help, contact wlan@cc.nthu.edu.tw with your device OS, location, SSID, account format, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming"""

EN_DORM_ACCOUNT_INCOMPLETE_ANSWER = """“Account application incomplete” usually means only the first part of the dormitory network process has been completed.

Dormitory network application has two parts:

**1. Apply for a dormitory network account**
This is done in the Academic Information System. Completing this step only creates the dormitory network account and password.

**2. Apply for dormitory network service**
After that, you still need to log in to the dormitory network application page, fill in your dormitory information, choose the application type, and submit the application. The system will then show your assigned IP settings.

If only step 1 is completed, the dormitory network service may still be considered incomplete. After the service application is submitted, applications are processed daily at 10:00 and 16:00.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_apply"""

EN_DORM_IP_ANSWER = """After your dormitory network application is complete and processed at 10:00 or 16:00, enter the assigned TCP/IP settings in your device’s Ethernet network settings.

If you are using a router, ask “How do I connect a router to the dorm network?” For a computer directly connected by network cable, follow these steps:

1. Make sure the device is connected to the dormitory network wall port by network cable.
2. Open the device’s network settings and select Ethernet.
3. Edit the IP assignment setting.
4. Change automatic DHCP to manual or static IPv4.
5. Enter the assigned IP address, subnet mask, gateway, and DNS shown after your DormNet application, then save.
6. Test whether the device can access the Internet.

For help, contact dorms@cc.nthu.edu.tw with your dormitory room number, device OS, IP settings, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config"""

EN_CAMPUS_BUILDING_WIFI_ANSWER_TEMPLATE = """{place} is an NTHU campus location, so you can first try using NTHU campus Wi-Fi there.

On site, look for `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam` and connect using the normal campus Wi-Fi method. If the signal is weak, the SSID does not appear, or the connection fails, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_DORM_APPLY_ANSWER = """Dormitory network application has two main parts.

**Apply for a dormitory network account**

1. Log in to the Academic Information System.
2. In the left menu, open the Computer and Communication Center related services, then enter the Network Systems Division online service.
3. Click the Network Systems Division online service login link.
4. Select “Student Dormitory Network Account” and make sure the device you use to apply is connected from the NTHU network domain.
5. Read the campus network and dormitory network usage rules.
6. Set your dormitory network password and click “Agree”.
7. At this point, only the dormitory network account is created. Continue to the dormitory network application page.

**Apply for dormitory network service**

8. Log in to the dormitory network application page using the account and password you just set. Select DormNet Account as the email option.
9. Fill in your dormitory information and choose “Register” as the application type.
10. After submission, the system will show your dormitory network IP settings. Keep this information; you will need it when setting up the network.
11. After submission, the system processes applications daily at 10:00 and 16:00. The dormitory network can be used after processing is complete.

If you need help with IP settings, ask “How do I set the dormitory network IP?”

For help, contact dorms@cc.nthu.edu.tw with your dormitory room number, device OS, IP settings, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_apply
https://net.nthu.edu.tw/netsys/en:dormnet/"""

EN_DORM_ROUTER_ANSWER = """To connect a router to DormNet, connect the router WAN port to the dormitory network wall port and set the WAN connection type to static IP.

1. Connect the router WAN port to the dormitory network wall port.
2. Connect your computer or phone to the router. It may show no Internet connection before the WAN settings are complete.
3. Open the router management page. Common addresses include `192.168.1.1` or `192.168.0.1`, but use the address shown in your router manual.
4. In WAN, Internet, or external network settings, choose static IP.
5. Enter the IP address, subnet mask, gateway, and DNS settings assigned after your dormitory network application.
6. Save the settings and test whether your devices can access the Internet through the router.

For help, contact dorms@cc.nthu.edu.tw with your dormitory room number, router model, WAN settings screenshot, assigned IP settings, and error screenshot.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config2"""

EN_DORM_USELESS_ANSWER = """If DormNet worked a few days ago but suddenly cannot connect now, start by checking the service status and doing a cross-test.

**Check status first**
1. Check the IP / network status to see whether the connection was blocked because of copyright, security, or abnormal traffic issues.
2. Check whether the DormNet account or service is disabled.
3. Check the user port status to see whether the dormitory network equipment or the room network wall port may be abnormal.

**Do a cross-test**
1. Confirm that the network cable works.
2. Test your computer and network cable in another room where DormNet is known to work.
3. Ask a roommate or another student to connect their computer to your room's network wall port.
4. During testing, use the IP settings assigned to the network wall port being tested. A wrong IP setting can also prevent connection.

**How to judge the cause**
1. If your computer cannot connect even in another working room, the issue may be your computer, cable, or IP settings.
2. If another computer also cannot connect through your room's wall port, the issue may be your room network wall port, cabling, or DormNet equipment status.
3. If the status page shows blocked or disabled service, follow the reason shown there or contact DormNet for help.

**Get help**
If you still cannot identify the cause, contact dorms@cc.nthu.edu.tw with your dormitory and room number, device OS, IP settings, status query results, cross-test results, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/en:dormnet/"""

EN_DORM_ROUTER_TROUBLESHOOTING_ANSWER = """If the router still does not work after setting a static IP, check these items first.

1. Make sure the dormitory network cable is connected to the router WAN port, not a LAN port.
2. Make sure the WAN connection type is static IP, not automatic IP or DHCP.
3. Make sure the assigned IP address, subnet mask, gateway, and DNS are entered in the correct fields.
4. Check for typing mistakes in numbers, dots, and field order.
5. Test with a computer directly connected to the dormitory network wall port using the same assigned IP settings.
6. If the computer works directly but the router does not, the issue is likely the router WAN settings. If the computer also cannot connect, the issue may be the assigned IP settings, cable, wall port, or dormitory network service status.

For help, contact dorms@cc.nthu.edu.tw with your dormitory room number, router model, WAN settings screenshot, assigned IP settings, direct-connection test result, and error screenshot.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config2
https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config"""

EN_EXTERNAL_EDUROAM_QUALITY_ANSWER = """When `eduroam` is slow or unstable at another university, check both the account format and the local wireless environment.

**Check the account format**
1. For off-campus eduroam roaming, use `sStudentID@wlan.nthu.edu.tw`.
2. The password is your NTHU campus wireless LAN password, not necessarily your Academic Information System password.

**Check the local environment**
1. If login succeeds but the speed is slow, the issue may be related to signal strength, local access point load, or the visited university’s network condition.
2. Try moving to a location with stronger signal and reconnect to `eduroam`.
3. If the problem continues, record the visited university, building, floor, time, device OS, SSID, and screenshots.

For NTHU wireless account or roaming authentication issues, contact wlan@cc.nthu.edu.tw with the information above.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless"""

EN_SHUI_MU_ANSWER = """**Shui Mu Life Center**
Shui Mu Life Center is listed in the public-area wireless network coverage. You can try using NTHU campus Wi-Fi there.

If the signal is weak or connection fails, contact wlan@cc.nthu.edu.tw with the location, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_HONG_ZHI_ZHI_ANSWER = """Hong Zhi Zhi steak is an off-campus restaurant, so it is not part of NTHU campus wireless network coverage.

If you are near Hong Zhi Zhi and need Internet access, use the restaurant’s own network if available or mobile data. NTHU campus Wi-Fi cannot be guaranteed outside campus coverage.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy"""

EN_STUDENT_EMAIL_ANSWER = """**Student email application**

1. Log in to the Academic Information System.
2. In the left menu, open the Computer and Communication Center related services, then enter the Network Systems Division online service.
3. Click the Network Systems Division online service login link.
4. Select “Student Email Application” and make sure the application is made from an NTHU campus IP address.
5. After reading and agreeing to the rules, the system will create a student email account. The format is `sStudentID@mAdmissionYear.nthu.edu.tw`, for example `s112345678@m112.nthu.edu.tw`. After the password is set and the application succeeds, the new mailbox should become available in about 10 minutes.

For details:
https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std"""

EN_STUDENT_EMAIL_FORMAT_ANSWER = """The NTHU student email address format is:

`sStudentID@mAdmissionYear.nthu.edu.tw`

For example, if the student ID is `112345678` and the admission year is `112`, the mailbox is:

`s112345678@m112.nthu.edu.tw`

For details:
https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std"""

EN_GAPP_ANSWER = """**G Suite for Education (gapp) account application**

1. Log in to the Academic Information System.
2. In the left menu, open the Computer and Communication Center related services, then enter the Network Systems Division online service.
3. Select “Google Apps Account Application”.
4. Read the required information, fill in your personal information and email address, then submit the application.

For details:
https://net.nthu.edu.tw/netsys/en:gapp#account_application_process"""

EN_EMAIL_APPLICATION_ANSWER = """NTHU has two common student email-related accounts: the student email account and the G Suite for Education (gapp) account.

**Student email account**
1. Log in to the Academic Information System.
2. Enter the Network Systems Division online service from the Computer and Communication Center related services menu.
3. Select “Student Email Application”.
4. Apply from an NTHU campus IP address.
5. The account format is `sStudentID@mAdmissionYear.nthu.edu.tw`, for example `s112345678@m112.nthu.edu.tw`.

**G Suite for Education (gapp) account**
1. Log in to the Academic Information System.
2. Enter the Network Systems Division online service.
3. Select “Google Apps Account Application”.
4. Read the required information, fill in your information, and submit.

For details:
https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std
https://net.nthu.edu.tw/netsys/en:gapp#account_application_process"""

EN_MAILBOX_FULL_ANSWER = """`Mailbox full` means the mailbox quota is full, so new mail may not be received normally.

**What to do**
1. Log in to the Webmail service for that mailbox.
2. Delete old mail that is no longer needed, especially messages with large attachments.
3. Check sent mail, drafts, and trash.
4. Empty the trash so deleted messages actually release mailbox space.
5. Test again after cleanup.

For details:
https://net.nthu.edu.tw/netsys/en:faq:mail_quota_size
https://net.nthu.edu.tw/netsys/en:faq:mail_quota_exceed"""

EN_DORM_IP_LOOKUP_ANSWER = """If you forgot your DormNet IP address, or want to check the IP/TCP/IP settings currently assigned to you, use the DormNet application status lookup page.

**How to check**
1. Open the DormNet application status lookup page:
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl
2. Log in with the DormNet account and password you previously set in the Academic Information System under Network Systems Division online service.
3. For the account type or email field, select “DormNet Account”.
4. After logging in, check your current DormNet application status and assigned IP/TCP/IP settings.

If you found the IP but do not know how to enter it, ask “How do I set the DormNet IP?” next.

**Get help**
If you cannot log in or cannot find your information, contact dorms@cc.nthu.edu.tw with your dorm and room number, account type selection screen, error message, and screenshots.

For details:
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless"""

EN_DORM_IP_STATUS_ANSWER = """If you need to check DormNet IP status, whether the IP is disabled, or why DormNet suddenly has abnormal connectivity, first follow the DormNet troubleshooting FAQ.

**Check status first**
1. Check IP / network status to confirm whether the IP is normal, blocked, or has abnormal records.
2. Check disabled status to see whether the connection was suspended due to DormNet usage rules or abnormal traffic.
3. Check user device port status to confirm whether the room network port or DormNet equipment may be abnormal.
4. If the status page shows a reason, follow the page instructions first. If you are not sure how to interpret it, send screenshots to DormNet support.

**If you forgot your IP**
Use the DormNet application status lookup page to view your assigned IP/TCP/IP settings:
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl

Log in with the DormNet account and password you set in the Academic Information System under Network Systems Division online service, and select “DormNet Account” as the account type.

**Get help**
If you still cannot determine the cause, contact dorms@cc.nthu.edu.tw with your dorm and room number, status screenshots, device OS, IP settings screen, and error message.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless
https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/MyApStatusM.pl"""

EN_NETWORK_SUPPORT_CONTACTS_ANSWER = """For NTHU network issues, use the support email for the relevant service.

**Campus Wi-Fi / wireless network**
Contact the wireless network service mailbox: wlan@cc.nthu.edu.tw

Include your location, SSID such as `nthu-cc`, `nthupeap`, `TANetRoaming`, or `eduroam`, device OS, error message, and screenshots.

**DormNet / dormitory network**
Contact the DormNet mailbox: dorms@cc.nthu.edu.tw

Include your dormitory and room number, device OS, whether IP settings are configured, IP settings screenshots, network status, error messages, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_useless
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless
https://net.nthu.edu.tw/netsys/en:dormnet/"""

EN_VPN_INTERNAL_IP_ANSWER = """If you are at home or off campus and need to access an NTHU service that is limited to on-campus IP addresses, use the NTHU VPN to connect back to the campus network.

**What to do**
1. Make sure you have a campus wireless LAN account and enable VPN if needed.
2. Download and install Ivanti Secure Access Client or Pulse Secure for your operating system.
3. Set the VPN server to `nthu.twaren.net`.
4. Log in with your campus wireless LAN account and password. The account format is `sStudentID@wlan.nthu.edu.tw`.
5. After the VPN connects, open the service that requires an on-campus IP address.

**Get help**
If the VPN cannot connect, contact wlan@cc.nthu.edu.tw with your OS, VPN client name, account format, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:sslvpn:info
https://net.nthu.edu.tw/netsys/en:sslvpn:sslvpn_setup
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp"""

EN_DORM_WIRED_NETWORK_SELECTION_ANSWER = """For wired Internet in a dormitory room, apply for DormNet, the dormitory network service.

**Which service to choose**
1. Wired Ethernet in a dormitory room: apply for DormNet.
2. Wireless Internet in classrooms, public areas, or department buildings: apply for campus Wi-Fi.
3. Off-campus access to services limited to on-campus IP addresses: use VPN.

**DormNet application summary**
1. In the Academic Information System, open Computer and Communication Center related services, then enter Network Systems Division online service.
2. Apply for the student DormNet account and set the DormNet password.
3. Then go to the DormNet application page, fill in dormitory information, and obtain the assigned IP settings.
4. Applications are processed daily at 10:00 and 16:00.
5. For a computer directly connected by Ethernet cable, enter the assigned TCP/IP settings.

If you are not sure how to set the IP, ask “How do I set the DormNet IP?” next.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_ua_apply
https://net.nthu.edu.tw/netsys/en:faq:domitory_net_apply
https://net.nthu.edu.tw/netsys/en:dormnet/"""

EN_VPN_ANSWER = """To connect to NTHU internal network resources from off campus, use the NTHU VPN service. First make sure your campus wireless LAN account has VPN enabled.

**Enable VPN for your account**
1. Log in to the Academic Information System.
2. Enter the Network Systems Division online service from the Computer and Communication Center related services menu.
3. Select “Wireless LAN Account”.
4. Fill in the required information and enable VPN in the VPN setting field.
5. The setting usually becomes effective in about 10 minutes.

**Set up the VPN client**
1. Download Ivanti Secure Access Client or Pulse Secure:
https://ndrive.niar.org.tw/navigate/a/#/s/894C6D3B91C94C3EB0D0B4237BC47B426BL
The download password is `nchc`.
2. Install the VPN client.
3. Open the VPN client and click `+`.
4. Enter `nthu.twaren.net` for both the name and server, then connect.
5. Log in with your campus wireless LAN account and password. The account format is `sStudentID@wlan.nthu.edu.tw`.
6. After authentication succeeds, you can access NTHU internal network resources.

For help, contact wlan@cc.nthu.edu.tw with your OS, VPN client name, account format, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:sslvpn:info
https://net.nthu.edu.tw/netsys/en:sslvpn:sslvpn_setup
https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp"""


def paired_fast_translations(answer: str) -> dict[str, str]:
    zh_quality_match = re.match(r"如果你在(.+?)連不到網路，或最近覺得網路很差，可以先從 Wi-Fi 名稱、訊號環境、認證與 IP 狀態這幾個方向檢查。", answer or "")
    if zh_quality_match:
        return {"en": build_english_wireless_quality_answer(zh_quality_match.group(1))}

    en_quality_match = re.match(r"If NTHU campus Wi-Fi at (.+?) is slow, unstable, or cannot connect", answer or "")
    if en_quality_match:
        place = chinese_place_name(en_quality_match.group(1))
        return {"zh-Hant": build_wireless_quality_answer(f"我在{place}網路很差")}

    location_pairs = {
        """**小吃部**
小吃部與小吃部戶外廣場列在公共區無線網路範圍中，可先嘗試使用校園無線網路。

若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy""": EN_CAFETERIA_WIFI_ANSWER,
        """**水木生活中心**
水木生活中心列在公共區無線網路範圍中，可先嘗試使用校園無線網路。

若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy""": EN_SHUI_MU_ANSWER,
        """**風雲樓**
風雲樓列在公共區無線網路範圍中，可先嘗試使用校園無線網路。

若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy""": EN_FENGYUN_WIFI_ANSWER,
        """**梅園**
目前資料無法確認梅園列在校園無線網路涵蓋範圍中。若在梅園現場搜尋不到 `nthu-cc`、`nthupeap`、`TANetRoaming` 或 `eduroam`，通常表示該處可能沒有清大 Wi-Fi 覆蓋或訊號太弱，建議移到鄰近有涵蓋的室內或公共區再測試。

若現場訊號弱或無法連線，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、連線的 SSID、裝置系統與錯誤畫面。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy""": EN_MEI_GARDEN_WIFI_ANSWER,
        """紅吱吱牛排等校外餐廳不屬於清大校園無線網路涵蓋範圍，因此沒有清大校園無線網路。

如果是在紅吱吱附近想使用網路，需以店家或一般行動網路為主；清大校園無線網路無法保證涵蓋校外餐廳。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy""": EN_HONG_ZHI_ZHI_ANSWER,
    }
    if answer in location_pairs:
        return {"en": location_pairs[answer]}
    for zh_answer, en_answer in location_pairs.items():
        if answer == en_answer:
            return {"zh-Hant": zh_answer}

    if answer.startswith("如果你忘記自己的宿網 IP"):
        return {"en": EN_DORM_IP_LOOKUP_ANSWER}
    if answer.startswith("If you forgot your DormNet IP address"):
        return {"zh-Hant": DORM_IP_LOOKUP_ANSWER}
    if answer.startswith("如果要查宿網 IP 狀態"):
        return {"en": EN_DORM_IP_STATUS_ANSWER}
    if answer.startswith("If you need to check DormNet IP status"):
        return {"zh-Hant": DORM_IP_STATUS_ANSWER}

    if answer.startswith("VPN 軟體登入時，密碼請填"):
        return {"en": EN_VPN_PASSWORD_ANSWER}
    if answer.startswith("When logging in to the VPN software") or answer.startswith("For the NTHU VPN client, enter the password"):
        return {"zh-Hant": VPN_PASSWORD_ANSWER}

    if answer.startswith("下載網址裡的 `22.7R2") or answer.startswith("下載網址中的資料夾名稱 `22.7R2"):
        return {"en": EN_VPN_DOWNLOAD_VERSION_ANSWER}
    if answer.startswith("The folders such as `22.7R2") or answer.startswith("The folder names `22.7R2"):
        return {"zh-Hant": VPN_DOWNLOAD_VERSION_ANSWER}

    if answer.startswith("**申請無線網路帳號**"):
        return {"en": EN_WIRELESS_APPLICATION_ANSWER}
    if answer.startswith("**Apply for a Wireless Network Account**") or answer.startswith("**Apply for a campus wireless LAN account**"):
        return {"zh-Hant": WIRELESS_APPLICATION_ANSWER}
    if answer.startswith("台積館可先嘗試使用清大校園無線網路"):
        return {"en": """At the TSMC Building, you can first try using the NTHU campus wireless network.

If you can find `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam` on site, connect using the normal campus Wi-Fi method. If the signal is weak, the campus Wi-Fi names do not appear, or the connection does not work, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy"""}
    if answer.startswith("At the TSMC Building") or answer.startswith("TSMC Building users"):
        return {"zh-Hant": """台積館可先嘗試使用清大校園無線網路。

若現場搜尋得到 `nthu-cc`、`TANetRoaming`、`nthupeap` 或 `eduroam`，即可依校園無線網路方式連線。若現場訊號弱、搜尋不到校園 Wi-Fi，或連線後無法使用，請向無線網路服務信箱 wlan@cc.nthu.edu.tw 提供所在位置、樓層、連線的 SSID、裝置系統與錯誤畫面，請技術人員協助確認。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:wlan_range
https://net.nthu.edu.tw/netsys/wireless:easy"""}

    if answer.startswith("無線網路帳號申請頁面無法進入時"):
        return {"en": EN_WIRELESS_APPLICATION_PAGE_ANSWER}
    if answer.startswith("If you cannot access the wireless network account application page"):
        return {"zh-Hant": WIRELESS_APPLICATION_PAGE_ANSWER}

    if answer.startswith("校園無線網路可以分成校內使用、外校漫遊與帳號申請來看。"):
        return {"en": EN_WIRELESS_USAGE_ANSWER}
    if answer.startswith("NTHU campus Wi-Fi can be used in two common ways."):
        return {"zh-Hant": WIRELESS_ANSWER}
    if answer == EXTERNAL_OR_AMBIGUOUS_NETWORK_ANSWER:
        return {"en": EN_EXTERNAL_OR_AMBIGUOUS_NETWORK_ANSWER}
    if answer == EN_EXTERNAL_OR_AMBIGUOUS_NETWORK_ANSWER:
        return {"zh-Hant": EXTERNAL_OR_AMBIGUOUS_NETWORK_ANSWER}

    pairs = (
        (WIRELESS_ANSWER, EN_WIRELESS_USAGE_ANSWER),
        (SEGMENTED_DORM_CONTEXT_ANSWER, EN_SEGMENTED_DORM_CONTEXT_ANSWER),
        (SEGMENTED_CAMPUS_LOCATION_ANSWER, EN_SEGMENTED_CAMPUS_LOCATION_ANSWER),
        (WIRELESS_APPLICATION_ANSWER, EN_WIRELESS_APPLICATION_ANSWER),
        (WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER, EN_WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER),
        (NETWORK_SUPPORT_CONTACTS_ANSWER, EN_NETWORK_SUPPORT_CONTACTS_ANSWER),
        (VPN_INTERNAL_IP_ANSWER, EN_VPN_INTERNAL_IP_ANSWER),
        (DORM_WIRED_NETWORK_SELECTION_ANSWER, EN_DORM_WIRED_NETWORK_SELECTION_ANSWER),
        (VPN_OPTIONAL_ANSWER, EN_VPN_OPTIONAL_ANSWER),
        (NTHU_CC_SWITCH_WIFI_ANSWER, EN_NTHU_CC_SWITCH_WIFI_ANSWER),
        (GAPP_EFFECTIVE_ANSWER, EN_GAPP_EFFECTIVE_ANSWER),
        (EXTERNAL_EDUROAM_FAILURE_ANSWER, EN_EXTERNAL_EDUROAM_FAILURE_ANSWER),
        (VPN_PASSWORD_ANSWER, EN_VPN_PASSWORD_ANSWER),
        (VPN_DOWNLOAD_VERSION_ANSWER, EN_VPN_DOWNLOAD_VERSION_ANSWER),
        (DORM_REPAIR_EMAIL_INFO_ANSWER, EN_DORM_REPAIR_EMAIL_INFO_ANSWER),
        (WIRELESS_APPLICATION_PAGE_ANSWER, EN_WIRELESS_APPLICATION_PAGE_ANSWER),
        (AMBIGUOUS_NETWORK_ANSWER, EN_AMBIGUOUS_NETWORK_ANSWER),
        (DORM_PORT_REPAIR_ANSWER, EN_DORM_PORT_REPAIR_ANSWER),
        (DORM_TRANSFER_CAUSE_ANSWER, EN_DORM_TRANSFER_CAUSE_ANSWER),
        (DORM_IP_LOOKUP_ANSWER, EN_DORM_IP_LOOKUP_ANSWER),
        (DORM_IP_STATUS_ANSWER, EN_DORM_IP_STATUS_ANSWER),
        (DORM_USELESS_ANSWER, EN_DORM_USELESS_ANSWER),
        (WIRELESS_CREDENTIAL_ANSWER, EN_WIRELESS_CREDENTIAL_ANSWER),
        (WIRELESS_PASSWORD_EFFECTIVE_ANSWER, EN_WIRELESS_PASSWORD_EFFECTIVE_ANSWER),
        (WIRELESS_TROUBLESHOOTING_ANSWER, EN_WIRELESS_QUALITY_ANSWER),
        (NTHU_CC_ANSWER, EN_NTHU_CC_ANSWER),
        (NTHU_CC_ANSWER, EN_NTHU_CC_LOGIN_PAGE_ANSWER),
        (TANETROAMING_ANSWER, EN_TANETROAMING_ANSWER),
        (EDUROAM_ANSWER, EN_EDUROAM_USAGE_ANSWER),
        (EDUROAM_ROAMING_ACCOUNT_ANSWER_ZH, EN_EDUROAM_ROAMING_ACCOUNT_ANSWER),
        (NTHUPEAP_ANSWER, EN_NTHUPEAP_ANSWER),
        (EDUROAM_FAILURE_ANSWER, EN_EDUROAM_FAILURE_ANSWER),
        (VPN_ANSWER, EN_VPN_ANSWER),
        (DORM_CONFIG_ANSWER, EN_DORM_IP_ANSWER),
        (DORM_APPLY_ANSWER, EN_DORM_APPLY_ANSWER),
        (DORM_ACCOUNT_INCOMPLETE_ANSWER, EN_DORM_ACCOUNT_INCOMPLETE_ANSWER),
        (ROUTER_ANSWER, EN_DORM_ROUTER_ANSWER),
        (ROUTER_TROUBLESHOOTING_ANSWER, EN_DORM_ROUTER_TROUBLESHOOTING_ANSWER),
        (EXTERNAL_EDUROAM_QUALITY_ANSWER, EN_EXTERNAL_EDUROAM_QUALITY_ANSWER),
        (EMAIL_APPLICATION_ANSWER, EN_EMAIL_APPLICATION_ANSWER),
        (STUDENT_EMAIL_APPLICATION_ANSWER, EN_STUDENT_EMAIL_ANSWER),
        (STUDENT_EMAIL_FORMAT_ANSWER, EN_STUDENT_EMAIL_FORMAT_ANSWER),
        (GAPP_APPLICATION_ANSWER, EN_GAPP_ANSWER),
        (MAILBOX_FULL_ANSWER, EN_MAILBOX_FULL_ANSWER),
    )
    for zh_answer, en_answer in pairs:
        if answer == zh_answer:
            return {"en": en_answer}
        if answer == en_answer:
            return {"zh-Hant": zh_answer}
    return {}


def build_fast_payload(answer: str, sources: list[dict[str, Any]], *, question: str) -> dict[str, Any]:
    cleaned_answer = clean_answer(answer, question=question)
    payload = {
        "answer": cleaned_answer,
        "sources": sources,
        "fast_answer": True,
    }
    translations = paired_fast_translations(answer) or paired_fast_translations(cleaned_answer)
    if translations:
        payload["answer_translations"] = {
            lang: clean_answer(translated, question=question)
            for lang, translated in translations.items()
        }
    return payload


def extract_english_building_name(question: str) -> str:
    cleaned = re.sub(r"^(?:does|is|can|do)\s+", "", question.strip(), flags=re.IGNORECASE)
    match = re.search(r"([A-Za-z0-9][A-Za-z0-9 ]{0,40}?\s+(?:building|hall|center|library))", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "This location"


def get_english_fast_answer(question: str) -> dict[str, Any] | None:
    normalized = normalize_text(question)
    result: tuple[str, list[dict[str, Any]]] | None = None

    if (
        any(term in normalized for term in ("campuswifi", "campuswi-fi", "wifi", "wi-fi", "wireless", "wlan"))
        and any(term in normalized for term in ("dormnet", "dormitorynetwork", "dormnetwork"))
        and any(term in normalized for term in ("supportemail", "supportemails", "email", "contact", "mailbox", "report"))
    ):
        result = (EN_NETWORK_SUPPORT_CONTACTS_ANSWER, [source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting."), source("en:faq:domitory_net_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless", "DormNet troubleshooting."), source("en:dormnet [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:dormnet/", "DormNet service.")])
    elif (
        any(term in normalized for term in ("offcampus", "off-campus", "home"))
        and any(term in normalized for term in ("oncampusonly", "on-campus-only", "campusonly", "campusip", "internalresource", "internalresources"))
    ):
        result = (EN_VPN_INTERNAL_IP_ANSWER, EN_VPN_SOURCES)
    elif (
        any(term in normalized for term in ("dormroom", "dormitoryroom", "dorm", "dormitory"))
        and any(term in normalized for term in ("wired", "ethernet", "networkcable", "cableinternet"))
        and any(term in normalized for term in ("dormnet", "wifi", "wi-fi", "vpn", "apply", "should", "which"))
    ):
        result = (EN_DORM_WIRED_NETWORK_SELECTION_ANSWER, EN_DORM_APPLY_SOURCES)
    elif is_no_credential_network_intent(question):
        result = (EN_WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER, EN_WIRELESS_NO_CREDENTIAL_SOURCES)
    elif "eduroam" in normalized and any(term in normalized for term in ("oncampus", "atnthu", "iamoncampus", "ioncampus")):
        result = (EN_EDUROAM_ON_CAMPUS_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("oncampus", "atnthu")) and any(term in normalized for term in ("sstudentid", "wlannthuedutw", "shouldiuse", "whichone", "account", "username")):
        result = (EN_EDUROAM_ON_CAMPUS_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif "vpn" in normalized and any(term in normalized for term in ("downloadfolder", "downloadfolders", "folder", "folders", "version", "versions", "number", "numbers", "227r2", "91r14", "91r17")):
        result = (EN_VPN_DOWNLOAD_VERSION_ANSWER, EN_VPN_SOURCES[:2])
    elif "vpn" in normalized and any(term in normalized for term in ("doialsoenable", "doihavetoenable", "doineedtoenable", "havetoenable", "alsoneedtoenable", "needtoenable", "shouldienable", "mustenable", "turnon", "enablevpn")):
        result = (EN_VPN_OPTIONAL_ANSWER, [EN_VPN_SOURCES[2], EN_VPN_SOURCES[0]])
    elif ("nthucc" in normalized or "nthu-cc" in question.lower()) and any(term in normalized for term in ("loginpagedoesnotappear", "loginpagewillnotappear", "loginpagewontappear", "loginpagecannotappear", "loginpagecantappear", "doesnotshow", "notshow", "noportal", "cannotredirect", "cantredirect")):
        result = (EN_NTHU_CC_LOGIN_PAGE_ANSWER, [source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting."), source("en:faq:wlan_auth [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_auth", "Wireless authentication settings.")])
    elif ("nthucc" in normalized or "nthu-cc" in question.lower()) and any(term in normalized for term in ("whichwifi", "whichssid", "switchto", "tryinstead")):
        result = (EN_NTHU_CC_SWITCH_WIFI_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif "eduroam" in normalized and any(term in normalized for term in ("anotheruniversity", "otheruniversity", "offcampus", "nycu", "ntu")) and has_network_failure_intent(question):
        result = (EN_EXTERNAL_EDUROAM_FAILURE_ANSWER, EN_EDUROAM_FAILURE_SOURCES)
    elif "eduroam" in normalized and has_network_failure_intent(question):
        result = (EN_EDUROAM_FAILURE_ANSWER, EN_EDUROAM_FAILURE_SOURCES)
    elif is_wireless_network_issue_intent(question):
        result = (EN_WIRELESS_QUALITY_ANSWER, [source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting."), source("en:faq:wlan_range [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_range", "Wireless coverage.")])
    elif ("nthucc" in normalized or "nthu-cc" in question.lower()) and any(term in normalized for term in ("use", "connect", "login", "signin", "how", "setting", "setup")):
        result = (EN_NTHU_CC_ANSWER, [source("en:faq:wlan_auth [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_auth", "Wireless authentication settings."), source("en:wireless:easy [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:easy", "Wireless network easy guide.")])
    elif "vpn" in normalized and any(term in normalized for term in ("password", "whatpassword", "whichpassword", "enterpassword", "typepassword", "passwordtoenter")):
        result = (EN_VPN_PASSWORD_ANSWER, [EN_VPN_SOURCES[2], EN_VPN_SOURCES[0]])
    elif "vpn" in normalized and any(term in normalized for term in ("accountformat", "username", "userid", "loginaccount", "whataccount", "whichaccount")):
        result = (EN_VPN_ACCOUNT_FORMAT_ANSWER, EN_VPN_SOURCES)
    elif any(term in normalized for term in ("forgotschoolnetworkpassword", "forgotnetworkpassword", "forgotwifipassword", "forgotwi-fipassword", "schoolnetworkpassword", "changeschoolnetworkpassword", "resetnetworkpassword", "resetwifipassword", "resetwi-fipassword")) or ("forgot" in normalized and "password" in normalized and any(term in normalized for term in ("wifi", "wireless", "network"))):
        result = (EN_WIRELESS_PASSWORD_RESET_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("wifi怎麼申請", "wifi要怎麼申請", "wifi申請", "wi-fi怎麼申請", "wi-fi要怎麼申請", "wi-fi申請", "無線網路怎麼申請", "無線網路要怎麼申請", "無線網路申請", "申請wifi", "申請無線網路", "howdoiapplyforwifi", "howdoiapplyforwi-fi", "howdoiapplyforcampuswifi", "howdoiapplyforcampuswi-fi", "applyforwifi", "applyforwi-fi", "applyforcampuswifi", "applyforcampuswi-fi", "campuswifiapplication", "campuswi-fiapplication")):
        result = (EN_WIRELESS_APPLICATION_ANSWER, EN_WIRELESS_APPLICATION_SOURCES)
    elif "vpn" in normalized and any(term in normalized for term in ("haveto", "must", "required", "needto", "necessary", "enabletoo", "alsoenable")):
        result = (EN_VPN_OPTIONAL_ANSWER, [EN_VPN_SOURCES[2], EN_VPN_SOURCES[0]])
    elif any(term in normalized for term in ("dormnetrepairemail", "dormitorynetworkrepairemail", "whatshouldiincludeinadormnetrepairemail", "whatshouldiincludeintheemail", "whattoincludeintheemail")):
        result = (EN_DORM_REPAIR_EMAIL_INFO_ANSWER, [source("en:faq:domitory_net_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless", "DormNet troubleshooting."), source("en:dormnet [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:dormnet/", "DormNet service.")])
    elif any(term in normalized for term in ("applicationpagewillnotopen", "applicationpagewontopen", "applicationpagecannotopen", "applicationpagecantopen", "cannotopentheapplicationpage", "cantopentheapplicationpage", "whycan’tiopenthenthuwi-fiapplicationpage", "whycan'tiopenthenthuwi-fiapplicationpage", "wifiapplicationpage", "wirelessapplicationpage")):
        result = (EN_WIRELESS_APPLICATION_PAGE_ANSWER, [EN_WIRELESS_SOURCES[1], source("en:wireless:application:ccxp [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp", "Wireless application via Academic Information System.")])
    elif any(term in normalized for term in ("校園無線網路怎麼使用", "無線網路怎麼使用", "清大wifi怎麼使用", "wifi怎麼使用")):
        result = (EN_WIRELESS_USAGE_ANSWER, EN_WIRELESS_SOURCES)
    elif any(term in normalized for term in ("宿舍網路怎麼申請", "宿網怎麼申請", "申請宿舍網路", "申請宿網")):
        result = (EN_DORM_APPLY_ANSWER, EN_DORM_APPLY_SOURCES)
    elif any(term in normalized for term in ("清大信箱怎麼申請", "信箱怎麼申請", "申請信箱")):
        result = (EN_EMAIL_APPLICATION_ANSWER, EN_EMAIL_SOURCES)
    elif any(term in normalized for term in ("gapp申請完多久可以用", "gapp多久可以用", "gapp多久生效", "gapp什麼時候可以用", "gappaccountavailable", "howlongdoesittakeforthegapp", "gappbecomeavailable")):
        result = (EN_GAPP_EFFECTIVE_ANSWER, [EN_EMAIL_SOURCES[1]])
    elif any(term in normalized for term in ("gapp信箱怎麼申請", "gapp怎麼申請", "googleapps帳號申請")):
        result = (EN_GAPP_ANSWER, [EN_EMAIL_SOURCES[1]])
    elif any(term in normalized for term in ("nthupeap使用", "nthupeap怎麼用", "nthupeap登入", "nthupeap怎麼連")):
        result = (EN_NTHUPEAP_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("eduroam登入失敗", "eduroam連不上", "eduroam不能用", "eduroam無法登入")):
        result = (EN_EDUROAM_FAILURE_ANSWER, EN_EDUROAM_FAILURE_SOURCES)
    elif any(term in normalized for term in ("eduroam使用", "eduroam怎麼用", "eduroam登入", "eduroam怎麼連")):
        result = (EN_EDUROAM_USAGE_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif "vpn" in normalized or "校外連到學校網路" in normalized or "設定學校的vpn" in normalized:
        result = (EN_VPN_ANSWER, EN_VPN_SOURCES)
    elif "mailbox" in normalized and any(term in normalized for term in ("full", "quota", "space")):
        result = (EN_MAILBOX_FULL_ANSWER, EN_MAIL_QUOTA_SOURCES)
    elif "vpn" in normalized:
        result = (EN_VPN_ANSWER, EN_VPN_SOURCES)
    elif ("wifi" in normalized or "wi-fi" in normalized or "wireless" in normalized or "network" in normalized) and ("password" in normalized or "account" in normalized) and ("ais" in normalized or "academicinformation" in normalized or "same" in normalized):
        result = (EN_WIRELESS_PASSWORD_RESET_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif "tanetroaming" in normalized:
        result = (EN_TANETROAMING_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("networkport", "wallport", "ethernetport", "lanport")) and any(term in normalized for term in ("broken", "bad", "fail", "notwork", "doesnotwork", "repair")):
        result = (EN_DORM_PORT_REPAIR_ANSWER, [source("en:faq:domitory_net_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless", "DormNet troubleshooting."), source("en:dormnet [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:dormnet/", "DormNet service.")])
    elif any(term in normalized for term in ("shuimu", "shuimulifecenter", "fengyun", "fengyunbuilding", "library", "deltabuilding", "tsmcbuilding", "humanitiesandsocialsciencesbuilding", "building", "hall", "center")) and any(term in normalized for term in ("slow", "unstable", "bad", "poor", "notwork", "notworking", "cannotconnect", "cantconnect", "veryslow")):
        result = (EN_WIRELESS_QUALITY_ANSWER, [source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting."), source("en:faq:wlan_range [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_range", "Wireless coverage.")])
    elif any(term in normalized for term in ("cafeteria", "foodcourt", "snackbar")):
        result = (EN_CAFETERIA_WIFI_ANSWER, EN_WLAN_RANGE_SOURCES)
    elif any(term in normalized for term in ("meigarden", "meiyuan")):
        result = (EN_MEI_GARDEN_WIFI_ANSWER, EN_WLAN_RANGE_SOURCES)
    elif any(term in normalized for term in ("fengyun", "fengyunbuilding", "fengyunhall", "fengyunbuilding")):
        result = (EN_FENGYUN_WIFI_ANSWER, EN_WLAN_RANGE_SOURCES)
    elif any(term in normalized for term in ("hongzhizhi", "redsteak")):
        result = (EN_HONG_ZHI_ZHI_ANSWER, EN_WLAN_RANGE_SOURCES)
    elif any(term in normalized for term in ("shuimu", "shuimulifecenter")):
        result = (EN_SHUI_MU_ANSWER, EN_WLAN_RANGE_SOURCES)
    elif "nthupeap" in normalized and any(term in normalized for term in ("use", "connect", "login", "signin", "setting", "setup", "how")):
        result = (EN_NTHUPEAP_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif "eduroam" in normalized and any(term in normalized for term in ("see", "found", "available", "shows", "appears")):
        result = (EN_EDUROAM_ROAMING_ACCOUNT_ANSWER, EN_EDUROAM_ROAMING_SOURCES)
    elif "eduroam" in normalized and any(term in normalized for term in ("failed", "fail", "cannotlogin", "cantlogin", "can'tlogin", "notwork", "cannotconnect", "cantconnect", "can'tconnect", "loginproblem")):
        result = (EN_EDUROAM_FAILURE_ANSWER, EN_EDUROAM_FAILURE_SOURCES)
    elif "eduroam" in normalized and any(term in normalized for term in ("nycu", "ntu", "otheruniversity", "anotheruniversity", "offcampus")) and any(term in normalized for term in ("failed", "fail", "loginfailed", "cannotlogin", "cantlogin", "notwork", "cannotconnect")):
        result = (EN_EXTERNAL_EDUROAM_FAILURE_ANSWER, EN_EDUROAM_FAILURE_SOURCES)
    elif "eduroam" in normalized and any(term in normalized for term in ("nycu", "otheruniversity", "anotheruniversity", "offcampus")) and any(term in normalized for term in ("slow", "unstable", "disconnect", "failed", "notwork")):
        result = (EN_EXTERNAL_EDUROAM_QUALITY_ANSWER, EN_WIRELESS_SOURCES[:1] + [source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting.")])
    elif ("eduroam" in normalized or "anotheruniversity" in normalized or "otheruniversity" in normalized) and any(term in normalized for term in ("username", "account", "format", "enter", "type", "login", "signin")):
        result = (EN_EDUROAM_ROAMING_ACCOUNT_ANSWER, EN_EDUROAM_ROAMING_SOURCES)
    elif "eduroam" in normalized and any(term in normalized for term in ("use", "connect", "login", "signin", "setting", "setup", "how")):
        result = (EN_EDUROAM_USAGE_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("router", "staticip", "wan")) and any(term in normalized for term in ("stilldoesnotwork", "doesnotwork", "notwork", "failed", "cannotconnect", "followedthesteps")):
        result = (EN_DORM_ROUTER_TROUBLESHOOTING_ANSWER, EN_DORM_ROUTER_SOURCES)
    elif any(term in normalized for term in ("moveddorm", "moveddorms", "movingdorm", "movingdorms", "changedorm", "changedorms", "newdorm", "newroom", "movedfrom", "couldthatberelated", "couldmovingdormsberelated")) and any(term in normalized for term in ("dorm", "dormitory", "dormnet", "ruzhai", "ruzai", "xinzhai", "xinzai")):
        result = (EN_DORM_TRANSFER_CAUSE_ANSWER, EN_DORM_APPLY_SOURCES)
    elif any(term in normalized for term in ("dormitory", "dormnetwork", "dormitorynetwork", "dormnet", "ruzhai", "ruzai", "rudorm", "rudormitory", "dorm")) and any(term in normalized for term in ("suddenly", "worked", "fewdays", "today", "yesterday", "lastweek", "recently", "bad", "reallybad", "slow", "veryslow", "unstable", "whatmightbewrong", "cannotconnect", "cantconnect", "can'tconnect", "notconnect", "notwork", "doesnotwork", "nointernet", "donthaveinternet", "donothaveinternet", "have nointernet", "stopped", "disconnect")):
        result = (EN_DORM_USELESS_ANSWER, [source("en:faq:domitory_net_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_net_useless", "DormNet troubleshooting."), source("en:dormnet [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:dormnet/", "DormNet service.")])
    elif any(term in normalized for term in ("dormitorynetworkaccountapplicationincomplete", "dormitorynetworkapplicationincomplete", "accountapplicationincomplete")) or (any(term in normalized for term in ("dormitorynetwork", "dormnetwork", "dormnet")) and any(term in normalized for term in ("incomplete", "notcompleted", "notcomplete"))):
        result = (EN_DORM_ACCOUNT_INCOMPLETE_ANSWER, EN_DORM_APPLY_SOURCES[:2])
    elif any(term in normalized for term in ("dormitorynetwork", "dormnetwork", "dormnet")) and any(term in normalized for term in ("ipsetting", "ipsettings", "dormnetworkip", "dormitorynetworkip", "networkip", "enter", "where", "tcpip", "staticip")):
        result = (EN_DORM_IP_ANSWER, [source("en:faq:domitory_network_config [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config", "Dormitory network IP settings.")])
    elif any(term in normalized for term in ("dormitorynetwork", "dormnetwork", "dormnet")) and any(term in normalized for term in ("apply", "application", "register")):
        result = (EN_DORM_APPLY_ANSWER, EN_DORM_APPLY_SOURCES)
    elif "router" in normalized and any(term in normalized for term in ("dorm", "dormitory", "network", "connect", "setup", "set")):
        result = (EN_DORM_ROUTER_ANSWER, EN_DORM_ROUTER_SOURCES[:1])
    elif any(term in normalized for term in ("studentemailaddressformat", "studentmailboxformat", "studentmailformat", "nthustudentemailaddressformat")) or (any(term in normalized for term in ("studentmailbox", "studentemail", "studentmail", "notgapp", "notgoogle")) and any(term in normalized for term in ("format", "addressformat"))):
        result = (EN_STUDENT_EMAIL_FORMAT_ANSWER, [EN_EMAIL_SOURCES[0]])
    elif any(term in normalized for term in ("studentmailbox", "studentemail", "studentmail", "notgapp", "notgoogle")) and any(term in normalized for term in ("want", "only", "notgapp", "notgoogle", "apply", "application", "address")):
        result = (EN_STUDENT_EMAIL_ANSWER, [EN_EMAIL_SOURCES[0]])
    elif any(term in normalized for term in ("gapp", "googleapps", "googleworkspace")) and any(term in normalized for term in ("apply", "application", "account")) and "notgapp" not in normalized:
        result = (EN_GAPP_ANSWER, [EN_EMAIL_SOURCES[1]])
    elif any(term in normalized for term in ("email", "mail")) and any(term in normalized for term in ("apply", "application", "open", "account")):
        result = (EN_EMAIL_APPLICATION_ANSWER, EN_EMAIL_SOURCES)
    elif is_no_credential_network_intent(question):
        result = (EN_WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER, EN_WIRELESS_NO_CREDENTIAL_SOURCES)
    elif is_wireless_application_page_intent(question):
        result = (EN_WIRELESS_APPLICATION_PAGE_ANSWER, [EN_WIRELESS_SOURCES[1], source("en:wireless:application:ccxp [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:wireless:application:ccxp", "Wireless application via Academic Information System.")])
    elif any(term in normalized for term in ("wifiaccount", "wi-fiaccount", "wirelesslanaccount")) and any(term in normalized for term in ("apply", "application", "where")):
        result = (EN_WIRELESS_APPLICATION_ANSWER, EN_WIRELESS_APPLICATION_SOURCES)
    elif any(term in normalized for term in ("passwordchange", "passwordreset", "takeeffect", "effective", "howlongdoesittake", "howlong")) and any(term in normalized for term in ("wireless", "wifi", "wi-fi", "campusnetwork", "password")):
        result = (EN_WIRELESS_PASSWORD_EFFECTIVE_ANSWER, EN_WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("redzhizhi", "redzizi", "zhizhi", "steak")):
        result = (EN_HONG_ZHI_ZHI_ANSWER, EN_WLAN_RANGE_SOURCES)
    elif any(term in normalized for term in ("campuswifi", "campuswi-fi", "wifi", "wi-fi", "wireless")) and any(term in normalized for term in ("stilldoesnotwork", "stillnotwork", "doesnotwork", "notwork", "notworking", "followedthesteps", "afterfollowing")):
        result = (EN_WIRELESS_QUALITY_ANSWER, [source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting."), source("en:faq:wlan_range [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_range", "Wireless coverage.")])
    elif any(term in normalized for term in ("building", "hall", "center", "library")) and any(term in normalized for term in ("slow", "unstable", "bad", "poor", "notwork", "notworking", "cannotconnect", "cantconnect", "veryslow")):
        result = (EN_WIRELESS_QUALITY_ANSWER, [source("en:faq:wlan_useless [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless", "Wireless troubleshooting."), source("en:faq:wlan_range [Network Systems Division]", "https://net.nthu.edu.tw/netsys/en:faq:wlan_range", "Wireless coverage.")])
    elif any(term in normalized for term in ("building", "hall", "center", "library")) and any(term in normalized for term in ("wifi", "wi-fi", "wireless", "network")):
        answer = EN_CAMPUS_BUILDING_WIFI_ANSWER_TEMPLATE.format(place=extract_english_building_name(question))
        result = (answer, EN_WLAN_RANGE_SOURCES)
    elif any(term in normalized for term in ("campuswifi", "campuswi-fi", "wireless", "wifi")) and any(term in normalized for term in ("use", "connect", "how")):
        result = (EN_WIRELESS_USAGE_ANSWER, EN_WIRELESS_SOURCES)

    if not result:
        return None
    answer, sources = result
    return build_fast_payload(answer, sources, question=question)


def get_structured_fast_answer(
    question: str,
    *,
    topic: str,
    intent: str,
    semantic_slots: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Route broad service intents from LangGraph state, after specific rules had a chance."""
    slots = semantic_slots or {}
    if (
        topic == "dorm_network"
        and slots.get("troubleshooting_stage") == "cross_test_failed"
    ):
        return build_fast_payload(
            DORM_CROSS_TEST_ESCALATION_ANSWER,
            DORM_USELESS_SOURCES,
            question=question,
        )
    if topic == "campus_wifi" and intent == "application":
        return build_fast_payload(
            WIRELESS_APPLICATION_ANSWER,
            [WIRELESS_SOURCES[2]],
            question=question,
        )
    if topic == "dorm_network" and (
        intent == "application" or slots.get("dorm_onboarding") == "true"
    ):
        return build_fast_payload(
            DORM_APPLY_ANSWER,
            DORM_APPLY_SOURCES,
            question=question,
        )
    return None


def get_dependency_fallback_answer(
    question: str,
    *,
    topic: str,
    intent: str,
    semantic_slots: dict[str, str] | None = None,
) -> dict[str, Any]:
    structured = get_structured_fast_answer(
        question,
        topic=topic,
        intent=intent,
        semantic_slots=semantic_slots,
    )
    if structured is not None:
        return structured

    known_intents = {
        ("dorm_network", "troubleshooting"): (DORM_USELESS_ANSWER, DORM_USELESS_SOURCES),
        ("dorm_network", "configuration"): (DORM_CONFIG_ANSWER, DORM_CONFIG_SOURCES),
        ("dorm_network", "application"): (DORM_APPLY_ANSWER, DORM_APPLY_SOURCES),
        ("campus_wifi", "application"): (WIRELESS_APPLICATION_ANSWER, [WIRELESS_SOURCES[2]]),
        ("campus_wifi", "configuration"): (WIRELESS_ANSWER, WIRELESS_SOURCES),
        ("vpn", "configuration"): (VPN_ANSWER, VPN_SOURCES),
        ("vpn", "application"): (VPN_ANSWER, VPN_SOURCES),
        ("email", "application"): (EMAIL_APPLICATION_ANSWER, EMAIL_APPLICATION_SOURCES),
    }
    known = known_intents.get((topic, intent))
    if known is not None:
        answer, sources = known
        return build_fast_payload(answer, sources, question=question)

    safe_answer = """目前暫時無法取得這個問題的完整資料，請稍後再試。

若問題緊急，可先從清大網路系統組官方 FAQ 查詢，或在問題中補充服務名稱、所在位置、裝置、錯誤訊息與已完成的排查結果，系統會優先提供可確認的處理方式。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq"""
    return build_fast_payload(
        safe_answer,
        [source("網路系統組 FAQ", "https://net.nthu.edu.tw/netsys/faq", "清大網路系統組官方常見問題。")],
        question=question,
    )


def get_fast_answer(question: str, has_history: bool = False) -> dict[str, Any] | None:
    if has_history:
        return None

    normalized = normalize_text(question)
    if (
        any(term in normalized for term in ("無線", "wifi", "wi-fi", "wlan", "校園網路", "學校網路"))
        and any(term in normalized for term in ("宿網", "宿舍網路", "宿舍有線網路"))
        and any(term in normalized for term in ("聯絡", "信箱", "找誰", "承辦", "服務信箱", "報修"))
    ):
        return build_fast_payload(NETWORK_SUPPORT_CONTACTS_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES + DORM_USELESS_SOURCES, question=question)
    if (
        any(term in normalized for term in ("校外", "家中", "家裡", "在家", "宿舍外", "offcampus", "home"))
        and any(term in normalized for term in ("校內ip", "校內資源", "限校內", "只有校內", "僅限校內", "校內服務", "校內才能", "內網", "onlyoncampus", "campusip", "internalresource"))
    ):
        return build_fast_payload(VPN_INTERNAL_IP_ANSWER, VPN_SOURCES, question=question)
    if all(term in normalized for term in ("nthupeap", "nthucc")) and any(
        term in normalized for term in ("還是", "只能", "都可以", "可以連", "哪個")
    ):
        return build_fast_payload(WIRELESS_ANSWER, WIRELESS_SOURCES, question=question)
    if (
        any(term in normalized for term in ("換宿", "換房間", "換了房間", "搬房間", "換寢室", "換了寢室", "搬寢室"))
        and any(term in normalized for term in ("宿網", "宿舍網路", "網路"))
        and any(term in normalized for term in ("不能用", "無法上網", "連不上", "連不到"))
    ):
        return build_fast_payload(DORM_TRANSFER_CAUSE_ANSWER, DORM_APPLY_SOURCES, question=question)
    if (
        any(term in normalized for term in ("宿舍房間", "宿舍", "寢室", "房間"))
        and any(term in normalized for term in ("有線網路", "網路線", "ethernet", "wired"))
        and any(term in normalized for term in ("宿網", "wifi", "wi-fi", "無線", "vpn", "哪個", "應該", "還是", "選", "申請"))
    ):
        return build_fast_payload(DORM_WIRED_NETWORK_SELECTION_ANSWER, DORM_APPLY_SOURCES + DORM_CONFIG_SOURCES, question=question)
    if (
        ("宿網" in normalized or "宿舍網路" in normalized or "網路孔" in normalized or any(term in question for term in DORM_BUILDING_TERMS))
        and (any(term in normalized for term in ("網路孔壞", "網路孔故障", "孔壞", "孔故障", "報修", "修理")) or (("網路孔" in normalized or "網孔" in normalized) and any(term in normalized for term in ("壞", "故障", "異常", "沒反應", "不能用"))))
    ):
        return build_fast_payload(DORM_PORT_REPAIR_ANSWER, DORM_USELESS_SOURCES, question=question)
    if any(term in normalized for term in ("宿網", "宿舍有線網路", "宿舍網路", "宿舍網路孔")) and any(term in normalized for term in ("聯絡", "信箱", "找誰", "報修")):
        return build_fast_payload(DORM_SUPPORT_CONTACT_ANSWER, DORM_USELESS_SOURCES, question=question)
    if (
        ("smtp" in normalized and any(term in normalized for term in ("校外", "驗證", "設定", "寄信")))
        or (
            any(term in normalized for term in ("學校信箱", "校內信箱", "清大信箱"))
            and any(term in normalized for term in ("寄不出去", "不能寄", "無法寄", "寄信失敗"))
            and any(term in normalized for term in ("校外", "家中", "家裡", "在家"))
        )
    ):
        return build_fast_payload(OFFCAMPUS_SMTP_ANSWER, [source("faq:mail_smtp_auth_outside_campus [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:mail_smtp_auth_outside_campus", "校外寄信與 SMTP AUTH。")], question=question)
    if any(term in normalized for term in ("假期自動回覆", "假期自動回信", "vacation")):
        return build_fast_payload(VACATION_REPLY_ANSWER, [source("mail:config:vacation [網路系統組]", "https://net.nthu.edu.tw/netsys/mail:config:vacation", "假期自動回信設定。")], question=question)
    if "gmail" in normalized and any(term in normalized for term in ("app", "收取", "收信", "設定", "郵件")):
        return build_fast_payload(GMAIL_APP_ANSWER, [source("mail:gmail_app [網路系統組]", "https://net.nthu.edu.tw/netsys/mail:gmail_app", "Gmail App 的 IMAP 與 SMTP AUTH 設定。")], question=question)
    if "webmail" in normalized and any(term in normalized for term in ("頁面", "哪裡", "網址", "使用", "登入")):
        return build_fast_payload(WEBMAIL_USAGE_ANSWER, [source("mail:webmail [網路系統組]", "https://net.nthu.edu.tw/netsys/mail:webmail", "清大 Webmail 服務入口。")], question=question)
    if "webmail" in normalized and any(term in normalized for term in ("自動登出", "登出", "踢出去", "踢出", "一直掉", "autologout")):
        return build_fast_payload(WEBMAIL_AUTO_LOGOUT_ANSWER, [source("faq:webmail:autologout [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:webmail:autologout", "Webmail 自動登出說明。")], question=question)
    if any(term in normalized for term in ("黑白名單", "黑名單", "白名單")) and any(term in normalized for term in ("郵件", "信箱", "垃圾信", "mail")):
        return build_fast_payload(MAIL_BLACK_WHITE_LIST_ANSWER, [source("faq:mail_white_black_address [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:mail_white_black_address", "個人化郵件黑白名單設定。")], question=question)
    if all(term in normalized for term in ("宿網", "vpn")) and any(term in normalized for term in ("wifi", "wi-fi", "無線")):
        return build_fast_payload(NETWORK_SERVICE_SELECTION_ANSWER, DORM_APPLY_SOURCES[:1] + WIRELESS_SOURCES[:1] + VPN_SOURCES[:1], question=question)
    if "tanetroaming" in normalized and "eduroam" in normalized and any(term in normalized for term in ("不同", "差別", "差異", "有何")):
        return build_fast_payload(WIRELESS_ANSWER, WIRELESS_SOURCES, question=question)
    if "無法辨識的網路" in normalized and any(term in normalized for term in ("宿網", "宿舍")):
        return build_fast_payload(DORM_UNIDENTIFIED_NETWORK_ANSWER, [source("faq:domitory_network_adapter_reinstall [網路系統組]", "https://net.nthu.edu.tw/netsys/faq:domitory_network_adapter_reinstall", "重新安裝乙太網路介面卡。")], question=question)
    if any(term in normalized for term in ("學生信箱格式", "校內信箱格式", "清大學生信箱格式", "信箱格式是什麼")):
        return build_fast_payload(STUDENT_EMAIL_FORMAT_ANSWER, [EMAIL_APPLICATION_SOURCES[0]], question=question)

    if "梅園" in normalized and any(term in normalized for term in ("有網路嗎", "有wifi嗎", "有wi-fi嗎", "有無線網路嗎", "搜尋不到", "搜不到", "找不到", "看不到", "沒有出現", "nthucc", "nthu-cc")):
        loc = location_answer(question)
        if loc is not None:
            answer, sources = loc
            return build_fast_payload(answer, sources, question=question)

    if any(term in normalized for term in ("vpn下載版本", "vpn下載資料夾", "vpn版本號", "下載網址資料夾", "下載網址裡面的資料夾", "下載網址裡面的", "下載連結裡面的", "下載連結資料夾", "資料夾充滿數字", "資料夾都是數字", "版本號是什麼", "22.7r2", "227r2", "9.1r14", "91r14", "9.1r17", "91r17")):
        return build_fast_payload(VPN_DOWNLOAD_VERSION_ANSWER, VPN_SOURCES[:2], question=question)

    campus_range = build_campus_building_range_answer(question)
    if campus_range is not None:
        answer, sources = campus_range
        return build_fast_payload(answer, sources, question=question)

    if is_wireless_quality_question(question):
        return build_fast_payload(build_wireless_quality_answer(question), WIRELESS_TROUBLESHOOTING_SOURCES + WLAN_RANGE_SOURCES[:1], question=question)

    if is_no_credential_network_intent(question):
        return build_fast_payload(WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER, WIRELESS_NO_CREDENTIAL_SOURCES, question=question)
    if ("nthucc" in normalized or "nthu-cc" in question.lower()) and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連")):
        return build_fast_payload(NTHU_CC_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES, question=question)
    if "nthupeap" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連")):
        return build_fast_payload(NTHUPEAP_ANSWER, WIRELESS_SOURCES, question=question)
    if (
        ("eduroam" in normalized or any(term in normalized for term in ("外校", "別的學校", "其他學校")))
        and any(term in normalized for term in ("帳號", "格式", "輸入什麼", "要打什麼"))
    ):
        return build_fast_payload(EDUROAM_ROAMING_ACCOUNT_ANSWER_ZH, WIRELESS_SOURCES[:2], question=question)

    if "eduroam" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連")):
        return build_fast_payload(EDUROAM_ANSWER, WIRELESS_SOURCES, question=question)
    if "tanetroaming" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連")):
        return build_fast_payload(TANETROAMING_ANSWER, WIRELESS_SOURCES[:2], question=question)

    if is_dorm_ip_lookup_intent(question):
        return build_fast_payload(DORM_IP_LOOKUP_ANSWER, DORM_IP_LOOKUP_SOURCES, question=question)
    if is_dorm_ip_status_intent(question):
        return build_fast_payload(DORM_IP_STATUS_ANSWER, DORM_IP_LOOKUP_SOURCES, question=question)
    if any(term in normalized for term in ("宿網狀態去哪裡檢查", "宿網狀態要去哪裡檢查", "宿網狀態查詢在哪", "宿網狀態在哪裡看", "宿網要去哪裡檢查", "宿網去哪裡檢查", "宿網檢查狀態")):
        return build_fast_payload(DORM_STATUS_CHECK_ANSWER, DORM_USELESS_SOURCES, question=question)
    if is_dorm_network_issue_intent(question):
        return build_fast_payload(DORM_USELESS_ANSWER, DORM_USELESS_SOURCES, question=question)
    if is_dorm_network_account_intent(question):
        return build_fast_payload(DORM_ACCOUNT_PASSWORD_ANSWER, DORM_APPLY_SOURCES, question=question)
    if is_dorm_network_availability_intent(question):
        return build_fast_payload(DORM_AVAILABILITY_ANSWER, DORM_APPLY_SOURCES, question=question)

    result: tuple[str, list[dict[str, Any]]] | None = get_training_fast_answer(question, exact_only=True)

    if result:
        answer, sources = result
        return build_fast_payload(answer, sources, question=question)

    if any(term in normalized for term in ("nthucc登入頁沒有出現時可以改連哪個wifi", "nthucc登入頁沒有出現時可以改連哪個wi-fi", "nthucc登入頁沒有出現時可以換哪個wifi", "nthucc登入頁沒有出現時可以換哪個wi-fi", "nthu-cc登入頁沒有出現時可以改連哪個wifi", "nthu-cc登入頁沒有出現時可以改連哪個wi-fi")):
        result = (NTHU_CC_SWITCH_WIFI_ANSWER, WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("宿網報修寄信要附什麼", "報修寄信要附什麼", "寄信要附什麼", "信中要提供什麼", "信裡要提供什麼")):
        result = (DORM_REPAIR_EMAIL_INFO_ANSWER, DORM_USELESS_SOURCES)
    elif any(term in normalized for term in ("哪個wifi", "哪個wi-fi", "連哪個wifi", "連哪個wi-fi", "不知道我是連哪個")):
        result = (WIRELESS_ANSWER, WIRELESS_SOURCES)
    elif any(term in normalized for term in ("我想連學校wifi", "想連學校wifi", "我想連學校wi-fi", "想連學校wi-fi", "想連校園wifi", "想連校園wi-fi")):
        result = (WIRELESS_ANSWER, WIRELESS_SOURCES)
    elif ("登入頁" in normalized or "認證頁" in normalized) and any(term in normalized for term in ("跳不出", "不跳", "死都不跳", "出不來", "沒有", "沒出", "不出", "不顯示")):
        result = (NTHU_CC_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES)
    elif is_no_credential_network_intent(question):
        result = (WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER, WIRELESS_NO_CREDENTIAL_SOURCES)
    elif is_wireless_application_page_intent(question):
        result = (WIRELESS_APPLICATION_PAGE_ANSWER, WIRELESS_SOURCES[2:3] + [source("wireless:application:ccxp [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application:ccxp", "校務資訊系統申請無線區域網路帳號步驟。")])
    elif any(term in normalized for term in ("宿網狀態去哪裡檢查", "宿網狀態要去哪裡檢查", "宿網狀態查詢在哪", "宿網狀態在哪裡看", "宿網要去哪裡檢查", "宿網去哪裡檢查", "宿網檢查狀態")):
        result = (DORM_STATUS_CHECK_ANSWER, DORM_USELESS_SOURCES)
    elif is_dorm_network_issue_intent(question):
        result = (DORM_USELESS_ANSWER, DORM_USELESS_SOURCES)
    elif is_dorm_network_account_intent(question):
        result = (DORM_ACCOUNT_PASSWORD_ANSWER, DORM_APPLY_SOURCES)
    elif is_dorm_network_availability_intent(question):
        result = (DORM_AVAILABILITY_ANSWER, DORM_APPLY_SOURCES)
    elif any(term in normalized for term in ("申請頁打不開", "申請頁無法進入", "申請頁進不去", "申請頁開不了", "申請頁不能開", "申請頁面打不開", "申請頁面無法進入", "申請頁面進不去", "無線網路申請頁", "wifi申請頁", "wi-fi申請頁")):
        result = (WIRELESS_APPLICATION_PAGE_ANSWER, WIRELESS_SOURCES[2:3] + [source("wireless:application:ccxp [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application:ccxp", "校務資訊系統申請無線區域網路帳號步驟。")])
    elif any(term in normalized for term in ("wifi怎麼申請", "wifi要怎麼申請", "wifi申請", "wify怎麼申請", "wify要怎麼申請", "wify申請", "wi-fi怎麼申請", "wi-fi要怎麼申請", "wi-fi申請", "無線網路怎麼申請", "無線網路要怎麼申請", "無線網路申請", "申請wifi", "申請wi-fi", "申請無線網路")):
        result = (WIRELESS_APPLICATION_ANSWER, WIRELESS_SOURCES[2:3] + [source("wireless:application:ccxp [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application:ccxp", "校務資訊系統申請無線區域網路帳號步驟。")])
    elif "vpn" in normalized and any(term in normalized for term in ("密碼要填", "密碼填什麼", "密碼是什麼", "密碼要輸入", "密碼輸入", "要填什麼密碼", "填哪個密碼", "哪個密碼", "什麼密碼")):
        result = (VPN_PASSWORD_ANSWER, [VPN_SOURCES[2], VPN_SOURCES[0]])
    elif "vpn" in normalized and any(term in normalized for term in ("一定要開", "一定要打開", "也要開", "也要打開", "一起開", "要一起開", "也要一起開", "要開嗎", "要打開嗎", "必須開", "需要開", "一定要啟用", "必須啟用", "需要啟用")):
        result = (VPN_OPTIONAL_ANSWER, [VPN_SOURCES[2], VPN_SOURCES[0]])
    elif any(term in normalized for term in ("nthucc登入頁沒有出現時可以改連哪個wifi", "nthucc登入頁沒有出現時可以改連哪個wi-fi", "nthu-cc登入頁沒有出現時可以改連哪個wifi", "nthu-cc登入頁沒有出現時可以改連哪個wi-fi")):
        result = (NTHU_CC_SWITCH_WIFI_ANSWER, WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("目前問題我要怎麼連", "目前問題要怎麼連", "目前問題怎麼連", "目前問題怎麼用", "目前問題要怎麼用")):
        result = (WIRELESS_CONNECT_FOLLOWUP_ANSWER, WIRELESS_SOURCES[:1] + WLAN_RANGE_SOURCES[1:2])
    elif "mailboxfull" in normalized or (("信箱" in normalized or "mailbox" in normalized) and any(term in normalized for term in ("空間已滿", "容量已滿", "信箱已滿", "滿了", "爆了", "爆"))):
        result = (MAILBOX_FULL_ANSWER, MAIL_QUOTA_SOURCES)
    elif any(term in normalized for term in ("552", "5.3.4")) or (("附件" in normalized or "郵件" in normalized) and any(term in normalized for term in ("過大", "大小", "退回", "退信"))):
        result = (MAIL_LARGE_MESSAGE_ANSWER, MAIL_SIZE_SOURCES)

    elif "vpn" in normalized or "校外連到學校網路" in normalized or "校外連到校內" in normalized:
        result = (VPN_ANSWER, VPN_SOURCES)

    elif is_no_credential_network_intent(question):
        result = (WIRELESS_NO_CREDENTIAL_NETWORK_ANSWER, WIRELESS_NO_CREDENTIAL_SOURCES)

    elif is_dorm_network_issue_intent(question):
        result = (DORM_USELESS_ANSWER, DORM_USELESS_SOURCES)
    elif is_dorm_network_account_intent(question):
        result = (DORM_ACCOUNT_PASSWORD_ANSWER, DORM_APPLY_SOURCES)
    elif is_dorm_network_availability_intent(question):
        result = (DORM_AVAILABILITY_ANSWER, DORM_APPLY_SOURCES)

    elif (
        ("wifi" in normalized or "wi-fi" in normalized or "wify" in normalized or "無線" in normalized or "校園網路" in normalized or "學校網路" in normalized or any(term in normalized for term in ("人社院", "風雲樓", "水木", "小吃部", "醫輔", "台積館", "台達館", "圖書館")))
        and ("帳密" in normalized or "帳號密碼" in normalized or "帳號" in normalized or "密碼" in normalized)
        and not any(term in normalized for term in ("忘記", "改密碼", "重設", "變更", "多久", "生效"))
    ):
        result = (WIRELESS_CREDENTIAL_ANSWER, WIRELESS_SOURCES)
    elif any(term in normalized for term in ("改完多久會生效", "密碼改完多久", "多久會生效", "幾分鐘生效", "何時生效")) and any(term in normalized for term in ("無線", "wifi", "wi-fi", "學校網路", "網路", "密碼")):
        result = (WIRELESS_PASSWORD_EFFECTIVE_ANSWER, WIRELESS_SOURCES[:2])
    elif (
        "帳號密碼" in normalized
        or "帳密" in normalized
        or "忘記" in normalized
        or "密碼是什麼" in normalized
        or "改密碼" in normalized
        or "重設密碼" in normalized
        or "學校網路密碼" in normalized
        or "網路密碼" in normalized
    ) and any(term in normalized for term in ("無線", "wifi", "wi-fi", "清大學生", "學校網路", "網路密碼")):
        result = (WIRELESS_PASSWORD_ANSWER, WIRELESS_SOURCES)
    elif (
        ("宿網" in normalized or "宿舍網路" in normalized or "網路孔" in normalized or any(term in question for term in DORM_BUILDING_TERMS))
        and (any(term in normalized for term in ("網路孔壞", "網路孔故障", "孔壞", "孔故障", "報修", "修理")) or (("網路孔" in normalized or "網孔" in normalized) and any(term in normalized for term in ("壞", "故障", "異常", "沒反應", "不能用"))))
    ):
        result = (DORM_PORT_REPAIR_ANSWER, DORM_USELESS_SOURCES)
    elif (
        ("宿網" in normalized or "宿舍網路" in normalized or any(term in question for term in DORM_BUILDING_TERMS))
        and any(term in normalized for term in ("照著", "照你", "步驟", "還是不行", "仍不行", "不行", "沒用"))
        and not any(term in normalized for term in ("分享器", "路由器", "wan", "固定ip"))
    ):
        result = (DORM_USELESS_FOLLOWUP_ANSWER, DORM_USELESS_SOURCES)
    elif (
        ("宿網" in normalized or "宿舍網路" in normalized or any(term in question for term in DORM_BUILDING_TERMS))
        and ("無線網路" in normalized or "wifi" in normalized or "wi-fi" in normalized)
        and any(term in normalized for term in ("什麼關係", "無關", "不是問", "問宿網"))
    ):
        result = (DORM_CONTEXT_CORRECTION_ANSWER, DORM_USELESS_SOURCES)
    elif (
        ("分享器" in normalized or "路由器" in normalized or "wan" in normalized or "固定ip" in normalized)
        and any(term in normalized for term in ("不行", "還是不行", "不能用", "無法上網", "連不上", "沒用", "失敗", "不通"))
    ):
        result = (ROUTER_TROUBLESHOOTING_ANSWER, DORM_ROUTER_SOURCES + DORM_CONFIG_SOURCES)
    elif any(term in normalized for term in ("換宿", "換房間", "換了房間", "搬房間", "換寢室", "換了寢室", "搬寢室")) and any(term in normalized for term in ("可能", "有關", "關係", "連不上", "連不到", "不能用", "無法上網", "換到", "搬到", "重新登記")):
        result = (DORM_TRANSFER_CAUSE_ANSWER, DORM_APPLY_SOURCES)
    elif any(term in normalized for term in ("換宿", "換房間", "換了房間", "搬房間", "換寢室", "換了寢室", "搬寢室")) and ("宿網" in normalized or "宿舍網路" in normalized or "網路" in normalized):
        result = (DORM_TRANSFER_APPLY_ANSWER, DORM_APPLY_SOURCES)
    elif (
        ("宿網" in normalized or "宿舍網路" in normalized or any(term in question for term in DORM_BUILDING_TERMS))
        and not any(term in normalized for term in ("分享器", "路由器", "wan", "固定ip"))
        and has_network_failure_intent(question)
    ):
        result = (DORM_USELESS_ANSWER, DORM_USELESS_SOURCES)
    elif is_wireless_quality_question(question):
        result = (build_wireless_quality_answer(question), WIRELESS_TROUBLESHOOTING_SOURCES + WLAN_RANGE_SOURCES[:1])
    elif any(term in normalized for term in ("紅吱吱", "梅園", "小吃部", "水木", "人社院", "風雲樓", "醫輔")) and any(term in normalized for term in ("網路", "wifi", "wi-fi", "無線", "nthucc", "nthu-cc", "nthupeap", "eduroam", "tanetroaming", "連")):
        result = location_answer(question)
    elif any(term in normalized for term in ("外校eduroam登入失敗", "外校eduroam一直登入失敗", "台大eduroam登入失敗", "臺大eduroam登入失敗", "其他學校eduroam登入失敗")):
        result = (EXTERNAL_EDUROAM_FAILURE_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES + WIRELESS_SOURCES[:2])
    elif any(term in normalized for term in ("校外漫遊", "外校漫遊", "校際漫遊", "漫遊是什麼")):
        result = (ROAMING_ANSWER, WIRELESS_SOURCES)
    elif "tanetroaming" in normalized:
        result = (TANETROAMING_ANSWER, WIRELESS_SOURCES[:2])
    elif "eduroam" in normalized and any(term in normalized for term in ("交大", "陽明交大", "台大", "臺大", "政大", "成大", "外校", "別的學校", "其他學校")) and any(term in normalized for term in ("很慢", "慢", "不穩", "斷線", "連不上", "失敗", "不能用")):
        result = (EXTERNAL_EDUROAM_QUALITY_ANSWER, WIRELESS_SOURCES[:2] + WIRELESS_TROUBLESHOOTING_SOURCES)
    elif ("eduroam" in normalized or "外校" in normalized or "別的學校" in normalized or "其他學校" in normalized) and any(term in normalized for term in ("帳號", "格式", "打什麼", "輸入什麼", "要打什麼", "怎麼登入", "怎麼連")):
        result = (EDUROAM_ROAMING_ACCOUNT_ANSWER_ZH, WIRELESS_SOURCES[:2])
    elif "eduroam" in normalized and any(term in normalized for term in ("失敗", "連不上", "連不到", "無法連線", "不能用", "無法登入", "登入不了", "認證失敗", "密碼錯", "密碼錯誤", "密碼不對")):
        result = (EDUROAM_FAILURE_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES + WIRELESS_SOURCES[:2])
    elif "eduroam" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定")):
        result = (EDUROAM_ANSWER, WIRELESS_SOURCES)
    elif "nthupeap" in normalized and any(term in normalized for term in ("失敗", "連不上", "連不到", "無法連線", "不能用", "無法登入", "登入不了", "認證失敗")):
        result = (WIRELESS_TROUBLESHOOTING_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES)
    elif "nthupeap" in normalized and any(term in normalized for term in ("使用", "登入", "連", "設定")):
        result = (NTHUPEAP_ANSWER, WIRELESS_SOURCES)
    elif ("nthucc" in normalized or "nthu-cc" in question.lower()) and any(term in normalized for term in ("使用", "登入", "連", "設定", "怎麼用", "怎麼連")):
        result = (NTHU_CC_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES)
    elif (
        any(term in normalized for term in ("無線", "wifi", "wi-fi", "nthu-cc", "nthucc", "nthupeap", "eduroam", "學校網路", "學校wifi"))
        and has_network_failure_intent(question)
    ):
        result = (WIRELESS_TROUBLESHOOTING_ANSWER, WIRELESS_TROUBLESHOOTING_SOURCES)
    elif any(term in normalized for term in ("wifi怎麼申請", "wifi要怎麼申請", "wifi申請", "wify怎麼申請", "wify要怎麼申請", "wify申請", "wi-fi怎麼申請", "wi-fi要怎麼申請", "wi-fi申請", "無線網路怎麼申請", "無線網路要怎麼申請", "無線網路申請", "申請wifi", "申請wi-fi", "申請無線網路")):
        result = (WIRELESS_APPLICATION_ANSWER, WIRELESS_SOURCES[2:3] + [source("wireless:application:ccxp [網路系統組]", "https://net.nthu.edu.tw/netsys/wireless:application:ccxp", "校務資訊系統申請無線區域網路帳號步驟。")])
    elif any(term in normalized for term in ("校園無線網路怎麼使用", "無線網路怎麼使用", "清大wifi怎麼使用", "wifi怎麼使用")):
        result = (WIRELESS_ANSWER, WIRELESS_SOURCES)
    elif (
        any(term in normalized for term in ("ssid", "wifi名稱", "wi-fi名稱", "無線網路名稱"))
        and any(term in normalized for term in ("哪些", "有哪", "哪幾", "可以連", "可連", "清單"))
    ):
        result = (WIRELESS_ANSWER, WIRELESS_SOURCES)
    elif ("信箱" in normalized or "電子郵件" in normalized or "email" in normalized or "mail" in normalized) and any(term in normalized for term in ("爆", "滿", "容量", "空間")):
        result = (MAILBOX_FULL_ANSWER, MAIL_QUOTA_SOURCES)
    elif any(term in normalized for term in ("gapp申請完多久可以用", "gapp多久可以用", "gapp多久生效", "gapp什麼時候可以用")):
        result = (GAPP_EFFECTIVE_ANSWER, [EMAIL_APPLICATION_SOURCES[1]])
    elif ("學生信箱" in normalized or "校內信箱" in normalized or "不是gapp" in normalized or "不要gapp" in normalized) and any(term in normalized for term in ("信箱", "申請", "怎麼申請", "帳號", "怎麼開")):
        result = (STUDENT_EMAIL_APPLICATION_ANSWER, [EMAIL_APPLICATION_SOURCES[0]])
    elif (
        any(term in normalized for term in ("gapp", "googleapps", "googleworkspace", "google信箱", "gsuite"))
        and not any(term in normalized for term in ("不是gapp", "不要gapp"))
        and any(term in normalized for term in ("信箱", "申請", "怎麼申請", "帳號", "想辦", "要辦", "去哪辦", "哪裡辦", "申辦"))
    ):
        result = (GAPP_APPLICATION_ANSWER, [EMAIL_APPLICATION_SOURCES[1]])
    elif ("信箱" in normalized or "電子郵件" in normalized or "email" in normalized or "mail" in normalized or "gapp" in normalized) and any(term in normalized for term in ("申請", "怎麼申請", "帳號", "怎麼開")):
        result = (EMAIL_APPLICATION_ANSWER, EMAIL_APPLICATION_SOURCES)
    elif (
        ("分享器" in normalized or "路由器" in normalized)
        and any(term in normalized for term in ("不行", "還是不行", "不能用", "無法上網", "連不上", "沒用", "失敗", "不通"))
    ):
        result = (ROUTER_TROUBLESHOOTING_ANSWER, DORM_ROUTER_SOURCES + DORM_CONFIG_SOURCES)
    elif ("分享器" in normalized or "路由器" in normalized) and any(term in normalized for term in ("設定", "怎麼連", "連宿網", "宿網", "宿舍網路", "宿舍", "固定ip", "wan")):
        result = (ROUTER_ANSWER, DORM_ROUTER_SOURCES)
    elif is_dorm_ip_lookup_intent(question):
        result = (DORM_IP_LOOKUP_ANSWER, DORM_IP_LOOKUP_SOURCES)
    elif is_dorm_ip_status_intent(question):
        result = (DORM_IP_STATUS_ANSWER, DORM_IP_LOOKUP_SOURCES)
    elif (
        ("宿舍" in normalized or "宿網" in normalized or "dormnet" in normalized)
        and any(term in normalized for term in (
            "設定宿舍網路", "宿舍網路ip", "宿網ip", "ip怎麼設定", "ip設定",
            "tcpip", "tcpip設定", "網路tcpip", "固定ip", "手動ip",
            "乙太網路", "網路線怎麼設定", "宿網怎麼設定", "宿舍網路怎麼設定", "ip要填", "ip填", "ip要設"
        ))
    ):
        result = (DORM_CONFIG_ANSWER, DORM_CONFIG_SOURCES)
    elif (
        any(term in normalized for term in ("帳號未申請完成", "尚未申請完成", "沒有申請完成", "沒申請完成", "申請未完成"))
        and any(term in normalized for term in ("宿網", "宿舍網路", "學生宿舍網路帳號"))
    ):
        result = (DORM_ACCOUNT_INCOMPLETE_ANSWER, DORM_APPLY_SOURCES[:2])
    elif ("宿網" in normalized or "宿舍網路" in normalized) and any(term in normalized for term in ("申請", "怎麼申請", "去哪辦", "去哪裡辦", "哪裡辦", "去哪申請", "要去哪辦", "要辦", "怎麼辦", "重弄")):
        result = (DORM_APPLY_ANSWER, DORM_APPLY_SOURCES)
    elif is_wireless_quality_question(question):
        result = (build_wireless_quality_answer(question), WIRELESS_TROUBLESHOOTING_SOURCES + WLAN_RANGE_SOURCES[:1])
    else:
        result = location_answer(question)
        if result is None:
            result = build_campus_building_range_answer(question)

    if not result:
        result = get_training_fast_answer(question)

    if not result:
        return None

    answer, sources = result
    return build_fast_payload(answer, sources, question=question)
