import os

from dotenv import load_dotenv


load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
LLM_ENABLE_THINKING = os.getenv("LLM_ENABLE_THINKING", "true").lower() in {"1", "true", "yes", "on"}
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "medium")

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", OPENAI_API_KEY)
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", OPENAI_BASE_URL)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

SEARXNG_URL = os.getenv("SEARXNG_URL")
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "3"))

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "nthu_netsys_docs")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
RERANKER_URL = os.getenv("RERANKER_URL", "")
RERANKER_TIMEOUT = float(os.getenv("RERANKER_TIMEOUT", "8"))
RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", str(RAG_TOP_K)))

CRAWL4AI_URL = os.getenv("CRAWL4AI_URL", "")

NTHU_NETSYS_BASE_URL = os.getenv("NTHU_NETSYS_BASE_URL", "https://net.nthu.edu.tw/netsys/")
ZH_MAIN_REFERENCE_URLS = [
    "https://net.nthu.edu.tw/netsys/faq#學生宿舍網路問題",
    "https://net.nthu.edu.tw/netsys/faq#wireless",
    "https://net.nthu.edu.tw/netsys/mail:application_student:new_std",
    "https://net.nthu.edu.tw/netsys/gapp#帳號申請流程",
    "https://net.nthu.edu.tw/netsys/faq",
]
EN_MAIN_REFERENCE_URLS = [
    "https://net.nthu.edu.tw/netsys/en:faq#dormnet",
    "https://net.nthu.edu.tw/netsys/en:faq#wireless_network",
    "https://net.nthu.edu.tw/netsys/en:mail:application_student:new_std",
    "https://net.nthu.edu.tw/netsys/en:gapp#account_application_procedure",
    "https://net.nthu.edu.tw/netsys/en:faq",
]
MAIN_REFERENCE_URLS = [*ZH_MAIN_REFERENCE_URLS, *EN_MAIN_REFERENCE_URLS]
DETAIL_REFERENCE_URLS = [
    "https://net.nthu.edu.tw/netsys/faq:wlan_useless",
    "https://net.nthu.edu.tw/netsys/en:faq:wlan_useless",
]
NTHU_SEED_URLS = [
    url.strip()
    for url in os.getenv(
        "NTHU_SEED_URLS",
        ",".join([*MAIN_REFERENCE_URLS, *DETAIL_REFERENCE_URLS]),
    ).split(",")
    if url.strip()
]
NTHU_PRIORITY_URLS = [
    url.strip()
    for url in os.getenv(
        "NTHU_PRIORITY_URLS",
        ",".join([*MAIN_REFERENCE_URLS, *DETAIL_REFERENCE_URLS]),
    ).split(",")
    if url.strip()
]
CRAWL_MAX_PAGES = int(os.getenv("CRAWL_MAX_PAGES", "70"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
INGEST_EMBED_BATCH_SIZE = max(1, int(os.getenv("INGEST_EMBED_BATCH_SIZE", "8")))

DAILY_REFRESH_HOUR = int(os.getenv("DAILY_REFRESH_HOUR", "3"))
DAILY_REFRESH_MINUTE = int(os.getenv("DAILY_REFRESH_MINUTE", "0"))
REFRESH_SLEEP_SECONDS = int(os.getenv("REFRESH_SLEEP_SECONDS", "60"))

CHAT_MAX_CONCURRENT_REQUESTS = int(os.getenv("CHAT_MAX_CONCURRENT_REQUESTS", "50"))
LLM_MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "4"))
LLM_REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "120"))
EMBEDDING_REQUEST_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_REQUEST_TIMEOUT_SECONDS", "3"))
EMBEDDING_CIRCUIT_BREAKER_SECONDS = float(os.getenv("EMBEDDING_CIRCUIT_BREAKER_SECONDS", "30"))
DEPENDENCY_HEALTH_TIMEOUT_SECONDS = float(os.getenv("DEPENDENCY_HEALTH_TIMEOUT_SECONDS", "5"))

FEW_SHOT_MAX_EXAMPLES = int(os.getenv("FEW_SHOT_MAX_EXAMPLES", "1"))
RAG_CONTEXT_CHARS_PER_SOURCE = int(os.getenv("RAG_CONTEXT_CHARS_PER_SOURCE", "320"))
RAG_CONTEXT_TOTAL_CHARS = int(os.getenv("RAG_CONTEXT_TOTAL_CHARS", "1400"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "900"))
LLM_CONTINUATION_MAX_TOKENS = int(os.getenv("LLM_CONTINUATION_MAX_TOKENS", "260"))

ANSWER_CACHE_TTL_SECONDS = int(os.getenv("ANSWER_CACHE_TTL_SECONDS", "21600"))
ANSWER_CACHE_MAX_ITEMS = int(os.getenv("ANSWER_CACHE_MAX_ITEMS", "512"))
RAG_CACHE_TTL_SECONDS = int(os.getenv("RAG_CACHE_TTL_SECONDS", "21600"))
RAG_CACHE_MAX_ITEMS = int(os.getenv("RAG_CACHE_MAX_ITEMS", "1024"))
