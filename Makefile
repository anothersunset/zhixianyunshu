.PHONY: help smoke demo health seed sbom backend rag web clean all install-tools

# polish: Makefile 带帮助菜单 — 不依赖【make】也能走脚本, 如走了更快

help:
	@echo '智迁云枢 · 常用命令'
	@echo ''
	@echo '  make smoke           三路静态检 (提交前跑)'
	@echo '  make demo            一键拉 demo (6 步)'
	@echo '  make health          7 endpoint 验状态'
	@echo '  make seed            只拉数据集 (sakila/chinook/sales/cdc)'
	@echo '  make sbom            本地生 SBOM (需 syft)'
	@echo '  make install-tools   一键装装 CLI (仅 macOS brew)'
	@echo ''
	@echo '  make backend         启 Spring Boot (8080)'
	@echo '  make rag             启 FastAPI (8001)'
	@echo '  make web             启 Vite dev (5173)'
	@echo ''
	@echo '  make clean           清 build / node_modules / __pycache__'

smoke:
	bash scripts/smoke-test.sh

demo:
	bash scripts/demo-walkthrough.sh

health:
	bash scripts/healthcheck.sh

seed:
	docker compose -f zhiqian/deploy/datasets/docker-compose.yml up -d

sbom:
	@mkdir -p .sbom
	syft dir:. -o cyclonedx-json=.sbom/zhiqian.cdx.json
	@echo 'wrote .sbom/zhiqian.cdx.json'

backend:
	cd zhiqian/backend && ./mvnw spring-boot:run

rag:
	cd zhiqian/rag && uvicorn app.main:app --reload --port 8001

web:
	cd zhiqian/web && pnpm dev

install-tools:
	brew install git docker docker-compose openjdk@21 maven node pnpm python@3.12 mysql-client typst syft trivy cosign
	pip install edge-tts pyflakes

clean:
	rm -rf zhiqian/backend/target zhiqian/web/dist zhiqian/web/node_modules
	find zhiqian -type d -name __pycache__ -exec rm -rf {} +
	find zhiqian -type d -name .pytest_cache -exec rm -rf {} +

all: smoke
