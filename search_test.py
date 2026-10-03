from search import search_web


def search(query: str, limit: int = 3):
    results = search_web(query, limit)

    for item in results:
        print("title:", item.get("title"))
        print("url:", item.get("url"))
        print("content:", item.get("content"))
        print("-" * 50)


if __name__ == "__main__":
    search("清華大學")
