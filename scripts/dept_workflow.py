#!/usr/bin/env python3
"""
部门工作流台账系统 v1.0
授信审批部专用 — 6科室业务追踪 + 时效预警
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────
LEDGER_DIR = Path.home() / "贷审部台账"
LEDGER_FILE = LEDGER_DIR / "workflow_ledger.json"
ARCHIVE_DIR = LEDGER_DIR / "归档"
CONFIG_FILE = LEDGER_DIR / "config.json"

# 科室定义（编号 → 名称 + 负责人placeholder + SLA天数）
DEPARTMENTS = {
    "D1": {"name": "地产基建评审科", "sla_days": 3},
    "D2": {"name": "产业评审科", "sla_days": 3},
    "D3": {"name": "跨境评审科", "sla_days": 5},
    "D4": {"name": "投行金融市场评审科", "sla_days": 5},
    "D5": {"name": "普惠业务评审科", "sla_days": 2},
    "D6": {"name": "放款科", "sla_days": 1},
}

# 流程节点定义（顺序）
NODES = [
    "受理",
    "初审",
    "科室评审",
    "部级评审",
    "审批批复",
    "放款",
    "归档",
]

# ── 工具函数 ──────────────────────────────────────────────────────────

def load_ledger():
    if not LEDGER_FILE.exists():
        return {"items": [], "last_updated": None}
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_ledger(data):
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now().isoformat()
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def business_days_left(due_date_str, from_date=None):
    """计算距离截止日期剩余工作日（排除周末）"""
    if from_date is None:
        from_date = datetime.now().date()
    elif isinstance(from_date, str):
        from_date = datetime.fromisoformat(from_date).date()

    if isinstance(due_date_str, str):
        due = datetime.fromisoformat(due_date_str).date()
    else:
        due = due_date_str

    count = 0
    d = from_date
    while d < due:
        d += timedelta(days=1)
        if d.weekday() < 5:  # Mon-Fri
            count += 1
    return count

def warning_level(remaining_days):
    if remaining_days < 0:
        return "🔴 A级", "overdue"
    elif remaining_days <= 1:
        return "🔴 A级", "critical"
    elif remaining_days <= 2:
        return "🟡 B级", "warning"
    else:
        return "🟢 C级", "normal"

def format_date(d):
    if not d:
        return "-"
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d)
        except:
            return d
    return d.strftime("%Y-%m-%d")

def gen_id():
    return datetime.now().strftime("%Y%m%d%H%M%S")

# ── 业务记录操作 ──────────────────────────────────────────────────────

def add_item(fields):
    """fields: dict with keys"""
    data = load_ledger()
    item = {
        "id": gen_id(),
        "created_at": datetime.now().isoformat(),
        "history": [],
    }
    # 必填字段
    for k in ["dept", "customer", "amount", "type", "current_node"]:
        if k not in fields or not fields[k]:
            raise ValueError(f"缺少必填字段: {k}")

    for k, v in fields.items():
        item[k] = v

    # 自动计算截止日期（基于SLA）
    dept_code = item["dept"]
    sla = DEPARTMENTS.get(dept_code, {}).get("sla_days", 3)
    node = item["current_node"]
    node_idx = NODES.index(node) if node in NODES else 1
    # 每节点给SLA天数
    due_days = datetime.now() + timedelta(days=sla * (len(NODES) - node_idx))
    item["due_date"] = due_days.isoformat()
    item["sla_days"] = sla

    data["items"].append(item)
    save_ledger(data)
    return item["id"]

def advance_node(item_id, to_node, operator="system", note=""):
    """推进业务到下一节点"""
    data = load_ledger()
    for item in data["items"]:
        if item["id"] == item_id:
            now = datetime.now().isoformat()
            item["history"].append({
                "from": item["current_node"],
                "to": to_node,
                "time": now,
                "operator": operator,
                "note": note,
            })
            item["current_node"] = to_node
            # 重新计算截止日期
            dept_code = item["dept"]
            sla = DEPARTMENTS.get(dept_code, {}).get("sla_days", 3)
            node_idx = NODES.index(to_node) if to_node in NODES else 1
            due_days = datetime.now() + timedelta(days=sla * (len(NODES) - node_idx))
            item["due_date"] = due_days.isoformat()
            save_ledger(data)
            return True
    return False

def list_items(filter_dept=None, filter_level=None, show_all=False):
    """列出业务，附带时效预警等级"""
    data = load_ledger()
    rows = []
    for item in data["items"]:
        if not show_all and item.get("current_node") == "归档":
            continue
        remaining = business_days_left(item["due_date"])
        level, label = warning_level(remaining)
        row = {
            "id": item["id"],
            "dept": DEPARTMENTS.get(item["dept"], {}).get("name", item["dept"]),
            "dept_code": item["dept"],
            "customer": item.get("customer", "-"),
            "amount": item.get("amount", "-"),
            "type": item.get("type", "-"),
            "current_node": item["current_node"],
            "due_date": format_date(item.get("due_date")),
            "remaining": remaining,
            "level": level,
            "label": label,
            "assignee": item.get("assignee", "-"),
        }
        if filter_dept and item["dept"] != filter_dept:
            continue
        if filter_level and label != filter_level:
            continue
        rows.append(row)
    # 按剩余工作日排序（少的在前 = 紧急的在前）
    rows.sort(key=lambda x: x["remaining"])
    return rows

def stats():
    """部门统计"""
    data = load_ledger()
    items = data["items"]
    total = len(items)
    archived = sum(1 for i in items if i.get("current_node") == "归档")
    active = total - archived
    overdue = sum(1 for i in items if i.get("current_node") != "归档" and business_days_left(i.get("due_date")) < 0)
    warning = sum(1 for i in items if i.get("current_node") != "归档" and 0 <= business_days_left(i.get("due_date")) <= 2)
    return {
        "total": total, "archived": archived, "active": active,
        "overdue": overdue, "warning": warning,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

# ── 展示 ──────────────────────────────────────────────────────────────

def print_dashboard():
    st = stats()
    items = list_items(show_all=False)
    print(f"\n{'='*60}")
    print(f"  贷审部工作台账 Dashboard  ({st['as_of']})")
    print(f"{'='*60}")
    print(f"  总业务数: {st['total']}  |  在办: {st['active']}  |  已归档: {st['archived']}")
    print(f"  {'🔴 超时':<8}  {st['overdue']}  {'🟡 预警':<8}  {st['warning']}")
    print(f"{'-'*60}")
    print(f"  {'编号':<16} {'科室':<12} {'客户':<10} {'金额':<10} {'节点':<8} {'截止':<12} {'剩余':>4}  状态")
    print(f"{'-'*60}")
    for r in items[:30]:  # 最多显示30条
        print(f"  {r['id']:<16} {r['dept']:<12} {r['customer'][:8]:<10} {str(r['amount']):<10} {r['current_node']:<8} {r['due_date']:<12} {r['remaining']:>4}  {r['level']}")
    print(f"{'='*60}")

def print_item_detail(item_id):
    data = load_ledger()
    for item in data["items"]:
        if item["id"] == item_id:
            print(f"\n{'='*50}")
            print(f"  业务详情: {item_id}")
            print(f"{'='*50}")
            for k, v in item.items():
                if k == "history":
                    print(f"  流转记录:")
                    for h in v:
                        print(f"    {h['time'][:10]}  {h['from']} → {h['to']}  [{h['operator']}] {h['note']}")
                elif k == "due_date":
                    print(f"  {k}: {format_date(v)}  (剩余 {business_days_left(v)} 工作日)")
                else:
                    print(f"  {k}: {v}")
            return
    print(f"未找到业务: {item_id}")

def print_dept_summary():
    """按科室统计"""
    data = load_ledger()
    print(f"\n{'='*50}")
    print(f"  科室业务统计")
    print(f"{'='*50}")
    for code, info in DEPARTMENTS.items():
        dept_items = [i for i in data["items"] if i.get("dept") == code]
        active = [i for i in dept_items if i.get("current_node") != "归档"]
        overdue = sum(1 for i in active if business_days_left(i.get("due_date")) < 0)
        warning = sum(1 for i in active if 0 <= business_days_left(i.get("due_date")) <= 2)
        print(f"  [{code}] {info['name']:<14}  总:{len(dept_items):>3}  在办:{len(active):>3}  超时:{overdue}  预警:{warning}")
    print(f"{'='*50}")

# ── CLI 入口 ───────────────────────────────────────────────────────────

def usage():
    print("""
用法:
  python3 dept_workflow.py list                    # 查看在办业务台账
  python3 dept_workflow.py all                      # 查看全部业务（含归档）
  python3 dept_workflow.py stats                    # 统计总览
  python3 dept_workflow.py dept                     # 按科室统计
  python3 dept_workflow.py add DEPT CUSTOMER AMOUNT TYPE NODE [ASSIGNEE]
                                                   # 新增业务
  python3 dept_workflow.py advance ID NODE [NOTE]  # 推进节点
  python3 dept_workflow.py detail ID               # 查看业务详情
  python3 dept_workflow.py export                  # 导出今日预警报告

示例:
  python3 dept_workflow.py add D5 某科技公司 500 科技贷款 科室评审 张三
  python3 dept_workflow.py advance 20250423102030 审批批复 批复已下达
  python3 dept_workflow.py list --dept D3          # 只看跨境科室
    """)

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        usage()
        sys.exit(0)

    cmd = args[0]

    if cmd == "list":
        dept_filter = None
        if "--dept" in args:
            idx = args.index("--dept")
            dept_filter = args[idx+1] if idx+1 < len(args) else None
        rows = list_items(filter_dept=dept_filter, show_all=False)
        if not rows:
            print("暂无在办业务")
        else:
            for r in rows:
                print(f"[{r['level']}] {r['id']} | {r['dept']} | {r['customer']} | {r['amount']}万 | {r['current_node']} | 截止{r['due_date']} | 剩{r['remaining']}日 | {r['assignee']}")

    elif cmd == "all":
        rows = list_items(show_all=True)
        for r in rows:
            print(f"[{r['level']}] {r['id']} | {r['dept']} | {r['customer']} | {r['amount']}万 | {r['current_node']} | 截止{r['due_date']} | 剩{r['remaining']}日")

    elif cmd == "stats":
        print_dashboard()

    elif cmd == "dept":
        print_dept_summary()

    elif cmd == "add":
        if len(args) < 6:
            print("参数不足: add DEPT CUSTOMER AMOUNT TYPE NODE [ASSIGNEE]")
            sys.exit(1)
        dept, customer, amount, btype, node = args[1:6]
        assignee = args[6] if len(args) > 6 else "未指定"
        node = node if node in NODES else NODES[2]  # 默认科室评审
        fid = add_item({
            "dept": dept,
            "customer": customer,
            "amount": amount,
            "type": btype,
            "current_node": node,
            "assignee": assignee,
        })
        print(f"✓ 业务已创建: {fid}")

    elif cmd == "advance":
        if len(args) < 3:
            print("参数不足: advance ID TO_NODE [NOTE]")
            sys.exit(1)
        item_id, to_node = args[1:3]
        note = args[3] if len(args) > 3 else ""
        ok = advance_node(item_id, to_node, note=note)
        print(f"{'✓ 节点已推进' if ok else '✗ 未找到业务'}")

    elif cmd == "detail":
        print_item_detail(args[1] if len(args) > 1 else "")

    elif cmd == "export":
        items = list_items(show_all=False)
        overdue = [r for r in items if r["label"] == "overdue"]
        critical = [r for r in items if r["label"] == "critical"]
        warning = [r for r in items if r["label"] == "warning"]
        report = f"""## 贷审部时效预警报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

### 超时业务（立即处理）
"""
        for r in overdue:
            report += f"- 🔴 [{r['dept']}] {r['customer']} | {r['amount']}万 | {r['current_node']} | 已超时{abs(r['remaining'])}日 | {r['assignee']}\n"
        report += f"\n### 临界预警（剩余≤1工作日）\n"
        for r in critical:
            report += f"- 🔴 [{r['dept']}] {r['customer']} | {r['amount']}万 | {r['current_node']} | 剩余{r['remaining']}日 | {r['assignee']}\n"
        report += f"\n### 一般预警（剩余≤2工作日）\n"
        for r in warning:
            report += f"- 🟡 [{r['dept']}] {r['customer']} | {r['amount']}万 | {r['current_node']} | 剩余{r['remaining']}日 | {r['assignee']}\n"
        print(report)

    else:
        usage()
