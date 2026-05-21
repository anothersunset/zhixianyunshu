# v2-step-11: RAG 服务 Makefile
# 常用目标:
#   make test-fast   — 不调 LLM / 不调外部服务, 几秒级 (retrieve + transpile + keyword)
#   make test-ragas  — 带 RAGAS, 需 DEEPSEEK_API_KEY
#   make test-all    — 全量
#   make coverage    — 生成 htmlcov/
#   make install-test — 装测试依赖
#   make serve       — 本地起 RAG (0.0.0.0:8001)

.PHONY: install install-test serve test-fast test-ragas test-all coverage clean

PY ?= python
PIP ?= $(PY) -m pip
PYTEST ?= $(PY) -m pytest

install:
	$(PIP) install -r requirements.txt

install-test:
	$(PIP) install -r requirements-test.txt

serve:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

test-fast:
	$(PYTEST) -v tests/test_retrieval.py tests/test_transpile.py -k 'not ragas'

test-ragas:
	$(PYTEST) -v tests/test_ragas.py

test-all:
	$(PYTEST) -v tests/

coverage:
	$(PYTEST) --cov=app --cov-report=html --cov-report=term tests/

clean:
	rm -rf htmlcov .pytest_cache .coverage
