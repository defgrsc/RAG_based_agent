from typing import Literal


GuardDecision = Literal["allow", "maybe", "deny"]


NTHU_KEYWORDS = (
    "nthu",
    "national tsing hua university",
    "清大",
    "清華",
    "清華大學",
    "國立清華大學",
    "新竹清華",
    "網路系統組",
    "校園網路",
    "campus wi-fi",
    "campus wifi",
    "campus wireless",
    "wireless lan",
    "宿舍網路",
    "宿網",
    "無線網路",
    "校園授權軟體",
    "電子郵件",
    "email",
    "vpn",
    "eduroam",
    "tanetroaming",
    "校外漫遊",
    "外校漫遊",
    "漫遊",
    "gapp",
    "google apps",
    "google workspace",
    "g suite",
)

# Dormitory names only; do not use the housing page as a source for non-network answers.
# Name reference: https://sthousing.site.nthu.edu.tw/p/412-1254-3455.php?Lang=zh-tw
DORM_BUILDING_KEYWORDS = (
    "明齋", "平齋", "清齋", "華齋", "誠齋", "義齋", "新齋", "禮齋",
    "仁齋", "實齋", "信齋", "碩齋", "學齋", "儒齋", "文齋", "靜齋",
    "慧齋", "雅齋", "鴻齋", "善齋", "鳴鳳樓", "崇善樓", "迎曦軒",
    "掬月齋", "樹德樓",
    "ru zhai", "ruzhai", "ru dorm", "ru dormitory", "ru residence hall",
    "xin zhai", "xinzhai", "xin dorm", "xin dormitory", "xin residence hall",
)

CAMPUS_LOCATION_KEYWORDS = (
    "人社院", "小吃部", "梅園", "資電館", "台達館", "台達", "台積館", "旺宏館", "圖書館",
    "總圖", "水木", "水木生活中心", "風雲樓", "醫輔大樓", "餐廳",
    "shui mu", "shuimu", "shui mu life center", "hong zhi zhi", "hongzhizhi", "red zhi zhi", "redzhizhi", "zhi zhi steak", "zhizhi steak", "red steak",
    "cafeteria", "food court", "snack bar", "mei garden", "meiyuan", "fengyun", "fengyun building",
    "學校哪裡", "校園哪裡", "學校其他地方", "其他學校地方",
)

EXTERNAL_NETWORK_CONTEXT_KEYWORDS = (
    "我公司", "公司的", "公司內網", "企業內網", "企業 vpn", "cisco vpn",
    "我家", "家裡", "家用網路", "其他學校", "外校 vpn",
)

NETWORK_SERVICE_KEYWORDS = (
    "網路",
    "上網",
    "連線",
    "連上",
    "斷線",
    "無法連",
    "連不上",
    "不能連",
    "登入失敗",
    "跳不出登入頁",
    "登入頁",
    "網頁",
    "認證",
    "帳號密碼",
    "帳密",
    "wifi",
    "wify",
    "wify",
    "wi-fi",
    "wireless",
    "ssid",
    "eduroam",
    "tanetroaming",
    "nthupeap",
    "校外漫遊",
    "外校漫遊",
    "漫遊",
    "nthu-cc",
    "vpn",
    "proxy",
    "dns",
    "ip",
    "mac",
    "網卡",
    "網孔",
    "網路孔",
    "網路線",
    "有線",
    "無線",
    "訊號",
    "品質",
    "很差",
    "不穩",
    "很慢",
    "宿舍",
    "寢室",
    "房間",
    "宿網",
    "宿舍網路",
    "校園網路",
    "電子郵件",
    "email",
    "mail",
    "webmail",
    "信箱",
    "郵件",
    "寄信",
    "收信",
    "退信",
    "附件",
    "mailbox",
    "gapp",
    "google apps",
    "google workspace",
    "g suite",
    "network",
    "dormnet",
    "dormitory network",
    "dorm network",
    "dormnet",
    "dormitory",
    "dorm",
    "router",
    "static ip",
    "wan",
    "campus wi-fi",
    "campus wifi",
    "wireless lan",
)

STRONG_NETWORK_KEYWORDS = tuple(
    keyword
    for keyword in NETWORK_SERVICE_KEYWORDS
    if keyword not in {"宿舍", "寢室", "房間"}
)

OFF_TOPIC_KEYWORDS = (
    "美食",
    "好吃",
    "餐廳",
    "宵夜",
    "天氣",
    "停車",
    "公車",
    "課程",
    "選課",
    "成績",
    "作業",
    "考試",
    "社團",
    "宿舍抽籤",
    "住宿費",
    "獎學金",
)


def classify_question(question: str) -> GuardDecision:
    normalized_question = question.lower().strip()

    if not normalized_question:
        return "deny"

    if "拒答" in normalized_question or "非清大網路問題" in normalized_question:
        return "deny"

    if any(keyword in normalized_question for keyword in EXTERNAL_NETWORK_CONTEXT_KEYWORDS):
        if "其他學校地方" not in normalized_question:
            return "deny"

    has_nthu_keyword = any(keyword in normalized_question for keyword in NTHU_KEYWORDS)
    has_dorm_building = any(keyword in normalized_question for keyword in DORM_BUILDING_KEYWORDS)
    has_network_intent = any(keyword in normalized_question for keyword in NETWORK_SERVICE_KEYWORDS)
    has_strong_network_intent = any(keyword in normalized_question for keyword in STRONG_NETWORK_KEYWORDS)
    has_off_topic_keyword = any(keyword in normalized_question for keyword in OFF_TOPIC_KEYWORDS)

    if has_off_topic_keyword and not has_strong_network_intent:
        return "deny"

    if any(term in normalized_question for term in ("網路孔壞", "網路孔故障", "孔壞", "孔故障", "網路孔報修", "網路孔要修", "網孔壞", "網孔故障")) or (("網路孔" in normalized_question or "網孔" in normalized_question) and any(term in normalized_question for term in ("壞", "故障", "異常", "沒反應", "不能用", "不能上網", "無法上網"))):
        return "allow"

    if any(term in normalized_question for term in ("network port", "wall port", "ethernet port", "lan port")) and any(term in normalized_question for term in ("broken", "bad", "not work", "doesn't work", "does not work", "repair")):
        return "allow"

    if has_dorm_building and has_network_intent:
        return "allow"

    if any(term in normalized_question for term in ("宿舍", "寢室", "房間")) and has_strong_network_intent:
        return "allow"

    if (
        any(term in normalized_question for term in ("校外", "家中", "家裡", "在家", "off campus", "off-campus", "home"))
        and any(term in normalized_question for term in ("校內 ip", "校內ip", "校內資源", "限校內", "僅限校內", "只有校內", "校內才能", "校內服務", "內網", "campus ip", "internal resource", "internal resources", "on-campus only", "on-campus-only", "campus-only"))
    ):
        return "allow"

    if any(keyword in normalized_question for keyword in CAMPUS_LOCATION_KEYWORDS) and has_network_intent:
        return "allow"

    if any(suffix in normalized_question for suffix in ("館", "院", "樓", "中心", "大樓")) and has_network_intent:
        return "allow"

    if any(term in normalized_question for term in ("哪裡有網路", "哪裡有wifi", "哪裡有wi-fi", "有網路嗎", "有wifi嗎", "有無線網路嗎")):
        return "allow"

    if any(term in normalized_question for term in ("building", "hall", "center", "library")) and any(term in normalized_question for term in ("wifi", "wi-fi", "wireless", "network")):
        return "allow"

    if has_nthu_keyword and has_network_intent:
        return "allow"

    if "學校" in normalized_question and has_strong_network_intent:
        return "allow"

    if "school" in normalized_question and any(term in normalized_question for term in ("network", "wifi", "wi-fi", "wireless", "vpn")) and any(term in normalized_question for term in ("password", "account", "login", "connect", "not working", "forgot", "reset", "change")):
        return "allow"

    if normalized_question in {"我網路不能用", "網路不能用", "我不能上網", "無法上網", "the school network is not working", "school network is not working"}:
        return "allow"

    if any(term in normalized_question for term in ("wifi", "wify", "wi-fi", "無線", "wireless", "tanetroaming")) and any(term in normalized_question for term in ("申請", "帳密", "帳號", "密碼", "怎麼用", "使用", "哪個", "連哪個", "比較好", "怎麼連", "連線", "apply", "application", "account", "password", "use", "open", "which", "connect")):
        return "allow"

    if ("信箱" in normalized_question or "mail" in normalized_question or "email" in normalized_question or "mailbox" in normalized_question) and any(term in normalized_question for term in ("爆", "滿", "容量", "空間", "full", "quota", "space")):
        return "allow"

    if any(term in normalized_question for term in ("dormitory network", "dorm network", "dormnet")):
        return "allow"

    if any(term in normalized_question for term in ("dormitory", "dorm", "residence hall")) and any(term in normalized_question for term in ("internet", "network", "connect", "not working", "no internet", "can't connect", "cannot connect", "wifi", "wi-fi")):
        return "allow"

    if any(term in normalized_question for term in ("router", "static ip", "wan")) and any(term in normalized_question for term in ("dorm", "network", "connect", "work", "not work", "setup", "set up")):
        return "allow"

    if "換宿" in normalized_question and has_network_intent:
        return "allow"

    if any(term in normalized_question for term in ("分享器", "路由器")) and any(term in normalized_question for term in ("設定", "怎麼連", "連線", "固定ip", "wan")):
        return "allow"

    return "deny"


def is_contextual_followup(question: str) -> bool:
    normalized = "".join(question.lower().split()).strip("？?!！。.")
    if normalized.endswith(("啊", "呀")):
        normalized = normalized[:-1]
    if normalized.startswith("那") and normalized.endswith(("呢", "勒", "咧", "哩")):
        return True
    ordinal_followup_prefixes = (
        "第一個", "第二個", "第三個", "第四個", "第五個", "第1個", "第2個", "第3個", "第4個", "第5個",
        "第一項", "第二項", "第三項", "第1項", "第2項", "第3項",
    )
    if normalized.startswith(ordinal_followup_prefixes) and normalized.endswith(("呢", "勒", "咧", "哩", "是什麼", "怎麼做", "怎麼辦", "怎麼用", "怎麼設定")):
        return True
    if normalized in {
        "怎麼連", "要怎麼連", "我要怎麼連", "怎麼用", "要怎麼用",
        "怎麼設定", "要怎麼設定", "怎麼申請", "要怎麼申請",
        "還是不能用", "還是連不上", "然後呢", "下一步呢",
        "那我要重新申請嗎", "改完多久會生效", "可是我現在人在校外",
        "人在校外", "wan那邊我到底要填什麼", "wan要填什麼",
        "how do i connect", "how can i connect", "how do i use it",
        "how do i set it up", "what is the next step", "what next",
        "the first one", "the second one", "the third one", "first one", "second one", "third one",
        "howdoiconnect", "howcaniconnect", "howdoiuseit",
        "howdoisetitup", "whatisthenextstep", "whatnext",
        "thefirstone", "thesecondone", "thethirdone", "firstone", "secondone", "thirdone",
        "iamoffcampusnow", "whatshouldienterforwansettings",
    }:
        return True

    contextual_terms = (
        "這個", "這是", "那個", "那是", "上面", "前面", "剛剛", "上述",
        "它", "他", "她", "意思", "是什麼", "為什麼", "怎麼辦", "怎麼處理",
        "未申請完成", "沒有申請完成", "沒申請完成", "尚未申請完成",
        "申請完成", "申請失敗", "申請不到", "不能申請", "無法申請",
        "重新申請", "重申請", "再申請", "申請嗎", "要申請", "要重新",
        "照著", "照你", "照你說", "步驟", "還是不行", "仍不行", "不行", "沒用",
        "不能用", "連不上", "無法上網", "失敗", "不通",
        "校外", "人在校外", "不在校內", "多久", "生效", "幾分鐘",
        "那邊", "搜尋不到", "搜不到", "找不到", "看不到", "沒有出現",
        "followed your steps", "followed the steps", "still does not work", "still doesn't work",
        "帳號", "密碼", "登入", "連線", "認證", "設定", "來源", "網址", "格式", "wan",
    )
    if any(term in normalized for term in contextual_terms):
        return True

    english_contextual_terms = (
        "what does", "what is", "why", "how", "account", "password",
        "login", "sign in", "connect", "connection", "apply", "application",
        "not completed", "failed", "include", "email", "what should i include", "username",
        "whatdoes", "whatis", "signin", "notcompleted", "whatshouldiinclude",
        "wansettings", "whatshouldienter", "offcampus", "iamoffcampusnow",
        "oncampus", "addressformat", "studentmailbox", "notgapp", "notgoogle",
        "howlong", "takeeffect", "effective", "reapply", "applyagain",
    )
    return any(term in normalized for term in english_contextual_terms)


def is_nthu_question(question: str) -> bool:
    return classify_question(question) == "allow"
