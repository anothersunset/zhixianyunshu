// v2-step-27: 迁移报告 Typst 模板。
// 调用: typst compile migration-report.typ output.pdf
// 本模板读同目录下 data.json。

#let data = json("data.json")

#set page(
  paper: "a4",
  margin: (x: 2.5cm, y: 2cm),
  header: align(right)[#text(size: 8pt, fill: gray)[智迁云枢迁移报告]],
  footer: align(center)[#text(size: 8pt, fill: gray)[第 #counter(page).display() 页]],
)

#set text(font: ("PingFang SC", "Noto Sans CJK SC", "SimSun", "Microsoft YaHei"), size: 11pt, lang: "zh")
#set par(justify: true, leading: 0.8em, first-line-indent: 2em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => block(above: 1.5em, below: 1em)[#text(size: 18pt, weight: "bold", fill: rgb("#0c66e4"))[#it.body]]
#show heading.where(level: 2): it => block(above: 1.2em, below: 0.6em)[#text(size: 14pt, weight: "bold")[#it.body]]

// 封面
#align(center)[
  #v(3cm)
  #text(size: 28pt, weight: "bold", fill: rgb("#0c66e4"))[数据库迁移评估报告]
  #v(1cm)
  #text(size: 16pt)[#data.project_name]
  #v(2cm)
  #grid(columns: 2, gutter: 1em, align: left,
    [源方言:], [#data.source_dialect],
    [目标方言:], [#data.target_dialect],
    [生成时间:], [#data.generated_at],
    [负责人:], [#data.owner],
  )
]

#pagebreak()

= 执行概要

#data.summary

#table(
  columns: 2,
  stroke: 0.5pt,
  align: (left, right),
  [总 SQL 语句数], [#data.stats.total_sql],
  [转译成功], [#data.stats.success],
  [需人工介入], [#data.stats.manual],
  [高风险], [#data.stats.high_risk],
  [表总数], [#data.stats.tables],
  [索引调整], [#data.stats.indexes_changed],
)

= 风险明细

#table(
  columns: (auto, 1fr, auto, auto),
  stroke: 0.5pt,
  align: (left, left, center, center),
  table.header[类型][说明][等级][建议],
  ..for r in data.risks {
    (r.kind, r.description, text(fill: if r.level == "高" {red} else if r.level == "中" {orange} else {green})[#r.level], r.suggestion)
  }
)

= SQL 转译示例

#for ex in data.examples [
  == #ex.title

  *源 SQL (#data.source_dialect)*:
  #block(
    fill: rgb("#f5f5f5"),
    inset: 8pt,
    radius: 4pt,
    width: 100%,
  )[#text(font: "Menlo", size: 9pt)[#raw(ex.source)]]

  *目标 SQL (#data.target_dialect)*:
  #block(
    fill: rgb("#e8f5e9"),
    inset: 8pt,
    radius: 4pt,
    width: 100%,
  )[#text(font: "Menlo", size: 9pt)[#raw(ex.target)]]

  *变动说明*: #ex.explanation

  #v(0.5em)
]

= 下一步建议

+ 在 staging 环境回放 #data.stats.total_sql 条语句。
+ 针对 #data.stats.high_risk 个高风险项指定人工复核。
+ 表结构调整 #data.stats.indexes_changed 项，需估算重建索引窗口。
+ 发微服务端互在 #data.target_dialect 运行性能基准。

#v(2cm)
#align(right)[
  #text(size: 10pt, fill: gray)[本报告由 ZhiQian YunShu 自动生成]
]
