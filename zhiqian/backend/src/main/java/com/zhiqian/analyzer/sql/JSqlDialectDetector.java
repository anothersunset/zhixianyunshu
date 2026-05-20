package com.zhiqian.analyzer.sql;

import com.zhiqian.analyzer.model.DialectResult;
import com.zhiqian.analyzer.model.SqlResult;
import net.sf.jsqlparser.JSQLParserException;
import net.sf.jsqlparser.parser.CCJSqlParserUtil;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.regex.Pattern;

@Component
public class JSqlDialectDetector {

	private static final Map<String, Pattern> ORACLE_FEATURES = Map.of(
		"ROWNUM",       Pattern.compile("\\bROWNUM\\b", Pattern.CASE_INSENSITIVE),
		"CONNECT_BY",   Pattern.compile("\\bCONNECT\\s+BY\\b", Pattern.CASE_INSENSITIVE),
		"NVL",          Pattern.compile("\\bNVL\\s*\\(", Pattern.CASE_INSENSITIVE),
		"SYSDATE",      Pattern.compile("\\bSYSDATE\\b", Pattern.CASE_INSENSITIVE),
		"MINUS_OP",     Pattern.compile("\\bMINUS\\b", Pattern.CASE_INSENSITIVE),
		"DUAL",         Pattern.compile("\\bFROM\\s+DUAL\\b", Pattern.CASE_INSENSITIVE),
		"PLSQL_BLOCK",  Pattern.compile("BEGIN\\s+.*\\s+END;", Pattern.DOTALL | Pattern.CASE_INSENSITIVE)
	);

	private static final Map<String, Pattern> MSSQL_FEATURES = Map.of(
		"TOP_N",        Pattern.compile("\\bSELECT\\s+TOP\\b", Pattern.CASE_INSENSITIVE),
		"GETDATE",      Pattern.compile("\\bGETDATE\\s*\\(", Pattern.CASE_INSENSITIVE),
		"ISNULL_FN",    Pattern.compile("\\bISNULL\\s*\\(", Pattern.CASE_INSENSITIVE),
		"BRACKET_IDENT",Pattern.compile("\\[[A-Za-z_][\\w]*\\]")
	);

	public DialectResult detect(SqlResult input) {
		List<DialectResult.Item> items = new ArrayList<>();
		for (var r : input.sqls()) {
			List<String> bad = new ArrayList<>();
			String dialect = "GENERIC";
			ORACLE_FEATURES.forEach((k, p) -> { if (p.matcher(r.text()).find()) bad.add("ORACLE:" + k); });
			MSSQL_FEATURES.forEach((k, p) -> { if (p.matcher(r.text()).find()) bad.add("MSSQL:" + k); });
			if (bad.stream().anyMatch(s -> s.startsWith("ORACLE:"))) dialect = "ORACLE";
			else if (bad.stream().anyMatch(s -> s.startsWith("MSSQL:"))) dialect = "MSSQL";

			boolean parseOk = tryParse(r.text());
			items.add(new DialectResult.Item(r, dialect, bad, parseOk));
		}
		return new DialectResult(items);
	}

	private boolean tryParse(String sql) {
		try { CCJSqlParserUtil.parse(sql); return true; }
		catch (JSQLParserException e) { return false; }
	}
}
