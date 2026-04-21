#!/usr/bin/env python3
"""上传文件到飞书云文档 - 使用Gateway进程凭证"""

import os
import sys

try:
    import lark_oapi as lark
    from lark_oapi.api.drive.v1.model.upload_all_file_request import UploadAllFileRequest
    from lark_oapi.api.drive.v1.model.upload_all_file_request_body import UploadAllFileRequestBody
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# 从环境变量获取凭证
APP_ID = os.environ.get("FEISHU_APP_ID")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FOLDER_TOKEN = "RdKwfZXLKlLwrSdSsN7cRSIunmh"

if not APP_ID or not APP_SECRET:
    print("ERROR: FEISHU_APP_ID or FEISHU_APP_SECRET not set")
    sys.exit(1)

print(f"Using APP_ID: {APP_ID}", file=sys.stderr)

def upload_file(file_path: str) -> dict:
    client = (
        lark.Client.builder()
        .app_id(APP_ID)
        .app_secret(APP_SECRET)
        .build()
    )
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    with open(file_path, "rb") as f:
        file_content = f.read()
    
    body = (
        UploadAllFileRequestBody.builder()
        .file_name(file_name)
        .parent_type("explorer")
        .parent_node(FOLDER_TOKEN)
        .size(file_size)
        .file(file_content)
        .build()
    )
    
    request = (
        UploadAllFileRequest.builder()
        .request_body(body)
        .build()
    )
    
    response = client.drive.v1.file.upload_all(request)
    
    if response.code != 0:
        return {"success": False, "error": f"code={response.code} msg={response.msg}"}
    
    file_token = getattr(response.data, "file_token", None) if response.data else None
    url = f"https://xxx.feishu.cn/drive/file/{file_token}" if file_token else None
    
    return {"success": True, "file_token": file_token, "url": url}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python feishu_upload.py <file_path>")
        sys.exit(1)
    
    result = upload_file(sys.argv[1])
    print(result)
