"""Deterministic corrective query rewriting for database-migration retrieval."""
from __future__ import annotations

import re
from typing import Optional


class QueryRewriter:
    """Normalize a query and add SQL migration terminology.

    The deterministic implementation keeps CI offline and makes the CRAG
    rewrite branch observable.  An optional LLM adapter may expose either a
    ``rewrite`` method or an ``invoke`` method; failures fall back to the rules.
    """

    _EXPANSIONS = (
        (re.compile(r"\b(ifnull|nvl|nvl2)\b", re.I), "COALESCE null handling function mapping"),
        (re.compile(r"\b(limit|offset|rownum|fetch\s+first)\b", re.I), "pagination syntax rewrite"),
        (re.compile(r"\b(auto_increment|identity|sequence)\b", re.I), "identity sequence type mapping"),
        (re.compile(r"\b(group_concat|string_agg|listagg)\b", re.I), "string aggregation function mapping"),
        (re.compile(r"\b(date_format|to_char|str_to_date)\b", re.I), "date time format function mapping"),
        (re.compile(r"\b(on\s+duplicate\s+key|on\s+conflict|merge\s+into)\b", re.I), "upsert conflict syntax rewrite"),
    )
    _DIALECTS = ("mysql", "oracle", "postgresql", "postgres", "opengauss", "sqlserver", "db2")

    def rewrite(self, question: str, llm: Optional[object] = None) -> str:
        query = re.sub(r"\s+", " ", (question or "").strip())
        if not query:
            return query

        llm_result = self._rewrite_with_llm(query, llm)
        if llm_result:
            return llm_result

        additions = [hint for pattern, hint in self._EXPANSIONS if pattern.search(query)]
        lowered = query.lower()
        if any(dialect in lowered for dialect in self._DIALECTS):
            additions.append("SQL dialect migration compatibility")
        if not additions:
            additions.append("database migration SQL dialect compatibility")
        unique = []
        for addition in additions:
            if addition.lower() not in lowered and addition not in unique:
                unique.append(addition)
        return " ".join([query, *unique]).strip()

    @staticmethod
    def _rewrite_with_llm(query: str, llm: Optional[object]) -> str:
        if llm is None:
            return ""
        try:
            if hasattr(llm, "rewrite"):
                value = llm.rewrite(query)
            elif hasattr(llm, "invoke"):
                value = llm.invoke(query)
                value = getattr(value, "content", value)
            else:
                return ""
            return re.sub(r"\s+", " ", str(value or "").strip())
        except Exception:  # noqa: BLE001
            return ""
