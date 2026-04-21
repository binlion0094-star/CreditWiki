#!/usr/bin/env python3
"""
飞书文档API创建文档并写入内容
使用 lark-oapi SDK
"""
import sys
import os

# 添加 venv path
sys.path.insert(0, '/Users/bismarck/.hermes/hermes-agent/venv/lib/python3.11/site-packages')

import lark_oapi as lark
from lark_oapi.core.model import Config
from lark_oapi.api.docx.v1.resource.document import Document
from lark_oapi.api.docx.v1.resource.document_block import DocumentBlock
from lark_oapi.api.docx.v1.resource.document_block_children import DocumentBlockChildren
from lark_oapi.api.docx.v1.model.create_document_request import CreateDocumentRequest
from lark_oapi.api.docx.v1.model.create_document_request_body import CreateDocumentRequestBody
from lark_oapi.api.docx.v1.model.create_document_block_children_request import CreateDocumentBlockChildrenRequest
from lark_oapi.api.docx.v1.model.create_document_block_children_request_body import CreateDocumentBlockChildrenRequestBody
from lark_oapi.api.docx.v1.model.get_document_block_request import GetDocumentBlockRequest
from lark_oapi.api.docx.v1.model.list_document_block_request import ListDocumentBlockRequest
from lark_oapi.api.docx.v1.model.block import Block
from lark_oapi.api.docx.v1.model.text import Text
from lark_oapi.api.docx.v1.model.text_element import TextElement
from lark_oapi.api.docx.v1.model.text_run import TextRun
from lark_oapi.api.docx.v1.model.text_element_style import TextElementStyle

# 加载 .env
def load_env():
    env_path = '/Users/bismarck/.hermes/.env'
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    os.environ[k] = v

load_env()

APP_ID = os.environ.get('FEISHU_APP_ID')
APP_SECRET = os.environ.get('FEISHU_APP_SECRET')

if not APP_ID or not APP_SECRET:
    print("ERROR: FEISHU_APP_ID or FEISHU_APP_SECRET not found in ~/.hermes/.env")
    sys.exit(1)

# 初始化配置
config = Config()
config.app_id = APP_ID
config.app_secret = APP_SECRET

# 测试文件
TEST_FILE = '/Users/bismarck/KnowledgeBase/CreditWiki/outputs/信贷审查_兴业银行_20260421.md'
DOC_TITLE = '信贷审查报告 - 兴业银行 601166'
FOLDER_TOKEN = None  # 不指定文件夹，走默认空间

def read_markdown_content(filepath):
    """读取markdown文件内容"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def create_text_run(text, bold=False):
    """创建TextRun（正确结构：TextRun -> TextElementStyle）"""
    if bold:
        style = TextElementStyle.builder().bold(True).build()
        return TextRun.builder().content(text).text_element_style(style).build()
    else:
        return TextRun.builder().content(text).build()

def create_text_elements(text, bold=False):
    """创建文本元素列表"""
    text_run = create_text_run(text, bold)
    return [TextElement.builder().text_run(text_run).build()]

def build_blocks_from_content(content):
    """将markdown内容拆分成多个文本块（使用Builder模式）"""
    blocks = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            # 空行用空格文本块
            text = Text.builder().elements([TextElement.builder().text_run(TextRun.builder().content(' ').build()).build()]).build()
            blocks.append(Block.builder().block_type(2).text(text).build())
            continue
        
        # 判断标题级别
        if line.startswith('### '):
            text_content = line[4:]
            text = Text.builder().elements(create_text_elements(text_content, bold=True)).build()
            blocks.append(Block.builder().block_type(5).heading3(text).build())
        elif line.startswith('## '):
            text_content = line[3:]
            text = Text.builder().elements(create_text_elements(text_content, bold=True)).build()
            blocks.append(Block.builder().block_type(4).heading2(text).build())
        elif line.startswith('# '):
            text_content = line[2:]
            text = Text.builder().elements(create_text_elements(text_content, bold=True)).build()
            blocks.append(Block.builder().block_type(3).heading1(text).build())
        elif line.startswith('- ') or line.startswith('* '):
            text_content = line[2:]
            text = Text.builder().elements(create_text_elements(text_content)).build()
            blocks.append(Block.builder().block_type(12).bullet(text).build())
        elif line.startswith('> '):
            text_content = line[2:]
            text = Text.builder().elements(create_text_elements(text_content)).build()
            blocks.append(Block.builder().block_type(15).quote(text).build())
        elif line.startswith('```'):
            continue
        else:
            text = Text.builder().elements(create_text_elements(line)).build()
            blocks.append(Block.builder().block_type(2).text(text).build())
    
    return blocks

def main():
    # 读取测试文件
    if not os.path.exists(TEST_FILE):
        print(f"ERROR: Test file not found: {TEST_FILE}")
        sys.exit(1)
    
    content = read_markdown_content(TEST_FILE)
    print(f"Read {len(content)} chars from {TEST_FILE}")
    
    # 步骤1：创建空白文档
    print("\n=== Step 1: Create Document ===")
    request = (CreateDocumentRequest.builder()
               .request_body(CreateDocumentRequestBody.builder()
                             .title(DOC_TITLE)
                             .folder_token(FOLDER_TOKEN)  # None = 默认空间
                             .build())
               .build())
    
    response = Document(config).create(request)
    
    if response.code != 0:
        print(f"ERROR: Failed to create document. code={response.code}, msg={response.msg}")
        sys.exit(1)
    
    doc_token = response.data.document.document_id
    print(f"SUCCESS: Document created! token={doc_token}")
    print(f"URL: https://feishu.cn/docx/{doc_token}")
    
    # 步骤2：获取文档根block ID
    print("\n=== Step 2: Get Root Block ID ===")
    request = (ListDocumentBlockRequest.builder()
               .document_id(doc_token)
               .build())
    response = DocumentBlock(config).list(request)
    
    if response.code != 0:
        print(f"ERROR: Failed to get blocks. code={response.code}, msg={response.msg}")
        sys.exit(1)
    
    root_block_id = response.data.items[0].block_id
    print(f"Root block ID: {root_block_id}")
    
    # 步骤3：写入内容块
    print("\n=== Step 3: Add Content Blocks ===")
    blocks = build_blocks_from_content(content)
    print(f"Built {len(blocks)} blocks from content")
    
    # 分批添加块（API有数量限制）
    BATCH_SIZE = 50
    for i in range(0, len(blocks), BATCH_SIZE):
        batch = blocks[i:i+BATCH_SIZE]
        print(f"Adding blocks {i+1} to {i+len(batch)}...")
        
        request = (CreateDocumentBlockChildrenRequest.builder()
                   .document_id(doc_token)
                   .block_id(root_block_id)
                   .request_body(CreateDocumentBlockChildrenRequestBody.builder()
                                 .children(batch)
                                 .build())
                   .build())
        
        response = DocumentBlockChildren(config).create(request)
        
        if response.code != 0:
            print(f"WARNING: code={response.code}, msg={response.msg}")
        else:
            print(f"  Added {len(batch)} blocks")
    
    print(f"\n=== DONE ===")
    print(f"Document URL: https://feishu.cn/docx/{doc_token}")

if __name__ == '__main__':
    main()
