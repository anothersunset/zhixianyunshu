# Typst PDF 报告 (v2-step-27)

## 依赖

```bash
brew install typst                # macOS
cargo install --locked typst-cli  # 跨平台
```

## API

```bash
curl http://localhost:8001/reports/status
# => {"typst_available": true}

curl -X POST http://localhost:8001/reports/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name":"Demo 项目",
    "source_dialect":"mysql","target_dialect":"opengauss",
    "generated_at":"2026-05-21","owner":"lee",
    "summary":"本次迁移覆盖 200 个表，预计业务中断 < 5 分钟。",
    "stats":{"total_sql":120,"success":110,"manual":10,"high_risk":3,"tables":200,"indexes_changed":18},
    "risks":[
      {"kind":"存储过程","description":"含动态 SQL EXECUTE IMMEDIATE","level":"高","suggestion":"拆为准备语句"},
      {"kind":"字符集","description":"utf8 → UTF8","level":"低","suggestion":"自动转换"}
    ],
    "examples":[
      {"title":"LIMIT 分页","source":"SELECT * FROM t LIMIT 5,10","target":"SELECT * FROM t LIMIT 10 OFFSET 5","explanation":"两段式转 standard SQL"}
    ]
  }' --output report.pdf
open report.pdf
```

## 模板位置

`app/reports/templates/migration-report.typ` — PingFang SC / Noto CJK 优先，Typst 0.10+ 语法。

## 为什么 Typst 不是 WeasyPrint / Pandoc

- 编译 < 1s，WeasyPrint 几秒。
- 语法 Markdown-like，比 LaTeX 友好。
- 中文原生支持，不需 xeCJK 几百行配置。
- 单二进制可部署，免装 TeX Live 3GB。
