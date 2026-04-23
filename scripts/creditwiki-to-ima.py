#!/usr/bin/env python3
"""
CreditWiki -> IMA Knowledge Base Sync
三步上传: create_media → COS上传 → add_knowledge

Usage:
  python creditwiki-to-ima.py --dry-run --limit 5
  python creditwiki-to-ima.py --kb "银行信贷"
  python creditwiki-to-ima.py --all
"""

import os, sys, json, argparse, time
from pathlib import Path

import requests
from qcloud_cos import CosConfig, CosS3Client

# IMA凭证
_config_dir = Path.home() / ".config" / "ima"
IMA_CLIENT_ID = os.environ.get("IMA_OPENAPI_CLIENTID",
    _config_dir.joinpath("client_id").read_text().strip() if _config_dir.joinpath("client_id").exists() else "")
IMA_API_KEY = os.environ.get("IMA_OPENAPI_APIKEY",
    _config_dir.joinpath("api_key").read_text().strip() if _config_dir.joinpath("api_key").exists() else "")

BASE_URL = "https://ima.qq.com"
WIKI_DIR = Path(__file__).parent.parent / "wiki"
SKIP_FILES = {"INDEX.md", "SUMMARY.md", "STATS.md", "TEMPLATE.md", "README.md"}


def ima_post(path, body):
    r = requests.post(f"{BASE_URL}/{path}",
        headers={
            "ima-openapi-clientid": IMA_CLIENT_ID,
            "ima-openapi-apikey": IMA_API_KEY,
            "Content-Type": "application/json",
        },
        json=body, timeout=30)
    return r.json()


def list_kbs():
    resp = ima_post("openapi/wiki/v1/search_knowledge_base",
                    {"query": "", "cursor": "", "limit": 20})
    if resp.get("code") != 0:
        print(f"  list_kbs error: {resp}")
        return []
    return resp.get("data", {}).get("info_list", [])


def get_root_folder_id(kb_id):
    r = ima_post("openapi/wiki/v1/get_knowledge_list",
                 {"knowledge_base_id": kb_id, "cursor": "", "limit": 1})
    data = r.get("data", {})
    path = data.get("current_path", [])
    return path[0]["folder_id"] if path else kb_id


def search_kb(name):
    kbs = list_kbs()
    nl = name.lower()
    for kb in kbs:
        if nl in kb.get("kb_name", "").lower():
            return kb["kb_id"], kb["kb_name"]
    if kbs:
        return kbs[0]["kb_id"], kbs[0]["kb_name"]
    return "", ""


def upload_markdown_to_ima(title, content_str, kb_id, folder_id):
    """三步上传Markdown到IMA: create_media → COS → add_knowledge"""
    file_size = len(content_str.encode("utf-8"))

    # Step 1: Create media
    r1 = ima_post("openapi/wiki/v1/create_media", {
        "file_name": title[:100] + ".md",
        "file_size": file_size,
        "content_type": "text/markdown",
        "knowledge_base_id": kb_id,
        "file_ext": "md",
    })
    if r1.get("code") != 0:
        return False, r1.get("msg", str(r1))

    media_id = r1["data"]["media_id"]
    cred = r1["data"]["cos_credential"]

    # Step 2: COS upload
    config = CosConfig(
        Region="ap-shanghai",
        SecretId=str(cred["secret_id"]),
        SecretKey=str(cred["secret_key"]),
        Token=str(cred["token"]),
        Appid=str(cred["appid"]),
    )
    client = CosS3Client(config)
    client.put_object(
        Bucket=cred["bucket_name"],
        Body=content_str.encode("utf-8"),
        Key=cred["cos_key"],
        ContentType="text/markdown",
    )

    # Step 3: Add knowledge
    r3 = ima_post("openapi/wiki/v1/add_knowledge", {
        "media_type": 7,
        "media_id": media_id,
        "title": title[:200],
        "knowledge_base_id": kb_id,
        "folder_id": folder_id,
        "file_info": {
            "cos_key": cred["cos_key"],
            "file_size": file_size,
            "last_modify_time": int(time.time()),
            "file_name": title[:100] + ".md",
        },
    })
    if r3.get("code") != 0:
        return False, r3.get("msg", str(r3))
    return True, r3.get("data", {}).get("media_id", "")


def get_recent_articles(limit=10):
    articles = []
    for subdir in WIKI_DIR.iterdir():
        if not subdir.is_dir() or subdir.name.startswith("."):
            continue
        for f in subdir.glob("*.md"):
            if f.name in SKIP_FILES:
                continue
            articles.append({"path": f, "mtime": f.stat().st_mtime})
    articles.sort(key=lambda x: x["mtime"], reverse=True)
    return articles[:limit]


def get_all_articles():
    articles = []
    for subdir in WIKI_DIR.iterdir():
        if not subdir.is_dir() or subdir.name.startswith("."):
            continue
        for f in subdir.glob("*.md"):
            if f.name in SKIP_FILES:
                continue
            articles.append({"path": f})
    return articles


def get_article_title(f):
    content = f.read_text(encoding="utf-8")
    parts = content.split("---")
    if len(parts) >= 3:
        try:
            import yaml
            fm = yaml.safe_load(parts[1].strip()) or {}
            t = fm.get("title", "")
            if t:
                return t
        except:
            pass
    for line in content.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return f.stem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb")
    parser.add_argument("--file")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not IMA_CLIENT_ID or not IMA_API_KEY:
        print("ERROR: Missing IMA credentials")
        sys.exit(1)

    print(f"ClientID: {IMA_CLIENT_ID[:8]}...")

    # Resolve KB
    if args.kb:
        kb_id, kb_name = search_kb(args.kb)
    else:
        kb_id, kb_name = search_kb("银行信贷")

    if not kb_id:
        print("ERROR: No KB found")
        sys.exit(1)
    folder_id = get_root_folder_id(kb_id)
    print(f"Target: {kb_name} | KB={kb_id[:20]}... | folder={folder_id}")

    # Collect files
    if args.file:
        files = [Path(args.file)]
    elif args.all:
        files = [a["path"] for a in get_all_articles()]
        print(f"Total: {len(files)} articles")
    else:
        files = [a["path"] for a in get_recent_articles(args.limit)]
        print(f"Recent: {len(files)} articles")

    if args.dry_run:
        print("\n[DRY RUN]")
        for f in files:
            print(f"  - {get_article_title(f)[:60]}")
        return

    # Upload
    success, skipped, failed = 0, 0, 0
    for f in files:
        title = get_article_title(f)
        content = f.read_text(encoding="utf-8")
        print(f"\nUploading: {title[:60]}...")

        ok, result = upload_markdown_to_ima(title, content, kb_id, folder_id)
        if ok:
            print(f"  OK: {result[:50]}...")
            success += 1
        else:
            print(f"  FAIL: {result}")
            failed += 1

    print(f"\nDone: {success} ok, {skipped} skip, {failed} fail")


if __name__ == "__main__":
    main()
