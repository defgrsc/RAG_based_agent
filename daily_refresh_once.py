from datetime import datetime

from ingest import ingest_nthu_docs


if __name__ == "__main__":
    print(f"Daily Refresh Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    result = ingest_nthu_docs(replace=True)
    print(f"Daily Refresh Finished: {result}", flush=True)
