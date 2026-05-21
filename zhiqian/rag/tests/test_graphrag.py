"""
v2-step-13: GraphRAG 单元测试。
固定 fixture: 15 个节点 + 18 边, 双社区 (order/payment), 验证:
- index() 返 n_nodes=15, n_edges=18, n_communities≥2
- query_local("OrderService") 命中 Class:OrderService, 邻居含 Method
- query_global("DATE_FORMAT 哪些模块用") 返含 order 社区
"""
import pytest

from app.graphs.graphrag import GraphRagIndex


@pytest.fixture
def ckg_fixture():
    nodes = [
        # Order 模块
        {"id": "f1", "type": "File", "label": "OrderService.java", "text": "订单服务 file"},
        {"id": "c1", "type": "Class", "label": "OrderService", "text": "订单业务逻辑"},
        {"id": "m1", "type": "Method", "label": "OrderService.queryByDate", "text": "按日期查询订单 DATE_FORMAT"},
        {"id": "m2", "type": "Method", "label": "OrderService.create", "text": "创建订单 IFNULL"},
        {"id": "t1", "type": "Table", "label": "t_order", "text": "订单表"},
        {"id": "col1", "type": "Column", "label": "t_order.create_time", "text": "datetime"},
        {"id": "col2", "type": "Column", "label": "t_order.amount", "text": "decimal"},
        # Payment 模块
        {"id": "f2", "type": "File", "label": "PaymentService.java", "text": "支付服务 file"},
        {"id": "c2", "type": "Class", "label": "PaymentService", "text": "支付业务逻辑"},
        {"id": "m3", "type": "Method", "label": "PaymentService.refund", "text": "退款 GROUP_CONCAT"},
        {"id": "m4", "type": "Method", "label": "PaymentService.pay", "text": "支付主流程 IFNULL"},
        {"id": "t2", "type": "Table", "label": "t_payment", "text": "支付表"},
        {"id": "col3", "type": "Column", "label": "t_payment.status", "text": "varchar"},
        # 独立节点 (独自一个社区)
        {"id": "f3", "type": "File", "label": "Utils.java", "text": "工具类"},
        {"id": "c3", "type": "Class", "label": "DateUtils", "text": "日期工具"},
    ]
    edges = [
        # Order 连通
        {"src": "f1", "dst": "c1", "type": "contains"},
        {"src": "c1", "dst": "m1", "type": "has_method"},
        {"src": "c1", "dst": "m2", "type": "has_method"},
        {"src": "m1", "dst": "t1", "type": "uses_table"},
        {"src": "m2", "dst": "t1", "type": "uses_table"},
        {"src": "t1", "dst": "col1", "type": "has_column"},
        {"src": "t1", "dst": "col2", "type": "has_column"},
        {"src": "m1", "dst": "col1", "type": "reads"},
        # Payment 连通
        {"src": "f2", "dst": "c2", "type": "contains"},
        {"src": "c2", "dst": "m3", "type": "has_method"},
        {"src": "c2", "dst": "m4", "type": "has_method"},
        {"src": "m3", "dst": "t2", "type": "uses_table"},
        {"src": "m4", "dst": "t2", "type": "uses_table"},
        {"src": "t2", "dst": "col3", "type": "has_column"},
        # Utils (孤立)
        {"src": "f3", "dst": "c3", "type": "contains"},
        # 跨模块弱关系 (让 order 与 payment 留独立)
        # 有意不连, 验证 community 能划出两馆
        {"src": "m1", "dst": "m1", "type": "self"},   # 自环应被过滤
        {"src": "m99", "dst": "m1", "type": "missing"},  # 错误节点应被过滤
        {"src": "m4", "dst": "col3", "type": "reads"},
    ]
    idx = GraphRagIndex(max_community_size=50)
    stats = idx.build(nodes, edges)
    return idx, stats


def test_index_stats(ckg_fixture):
    idx, stats = ckg_fixture
    assert stats["n_nodes"] == 15
    # 3 错误边 (self / missing src / missing src 重复) 应被过滤
    assert stats["n_edges"] >= 14
    # 至少 2 个社区: order / payment / utils
    assert stats["n_communities"] >= 2


def test_query_local_hit(ckg_fixture):
    idx, _ = ckg_fixture
    result = idx.query_local("OrderService queryByDate 怎么实现的")
    assert result["hits"], "应命中至少一个实体"
    labels = [e["label"] for e in result["entities"]]
    assert any("OrderService" in l or "queryByDate" in l for l in labels)
    assert "[HIT]" in result["context"]


def test_query_local_with_neighbors(ckg_fixture):
    idx, _ = ckg_fixture
    result = idx.query_local("queryByDate", max_entities=1, hop=1)
    assert result["hits"]
    assert result.get("neighbors"), "1-hop 邻居不能为空"


def test_query_local_no_hit(ckg_fixture):
    idx, _ = ckg_fixture
    result = idx.query_local("quantum chromodynamics nonsense xyz")
    assert result["hits"] == []
    assert result["context"] == ""


def test_query_global(ckg_fixture):
    idx, _ = ckg_fixture
    result = idx.query_global("DATE_FORMAT IFNULL 哪些模块用")
    assert result["reports"], "应命中社区报告"
    assert "##" in result["context"]


def test_query_global_empty_question(ckg_fixture):
    idx, _ = ckg_fixture
    result = idx.query_global("")
    assert result["reports"] == []


def test_community_reports_have_keywords(ckg_fixture):
    idx, _ = ckg_fixture
    for cid, rpt in idx.communities.items():
        assert rpt.id == cid
        assert rpt.keywords, f"社区 {cid} 缺关键词"
        assert rpt.node_ids
        assert rpt.type_breakdown


def test_stats_method(ckg_fixture):
    idx, _ = ckg_fixture
    s = idx.stats()
    assert s["n_nodes"] == 15
    assert s["largest_community"] >= 3
