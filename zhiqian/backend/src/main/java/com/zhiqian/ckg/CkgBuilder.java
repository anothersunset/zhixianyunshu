package com.zhiqian.ckg;

import com.zhiqian.analyzer.model.*;
import com.zhiqian.ckg.model.Ckg;
import com.zhiqian.ckg.model.CkgNode;
import org.apache.maven.model.Dependency;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 轻量内存版 CKG 构图器。
 * 节点类型：File / Class / Method / SQL / ConfigKey / Dependency
 * 边类型：DECLARES / CALLS / REFERS_TO / CONTAINS / DEPENDS_ON
 */
@Component
public class CkgBuilder {

    public Ckg build(PomResult pom, JavaResult java, SqlResult sql,
                     DialectResult dialect, ConfigResult cfg) {
        Ckg ckg = new Ckg();

        // Dependency
        if (pom != null && pom.dependencies() != null) {
            for (Dependency d : pom.dependencies()) {
                String ga = d.getGroupId() + ":" + d.getArtifactId();
                Map<String, Object> attrs = new HashMap<>();
                attrs.put("ga", ga);
                attrs.put("version", d.getVersion());
                attrs.put("risk", pom.riskDeps() != null && pom.riskDeps().stream()
                    .anyMatch(r -> ga.equals(r.ga())));
                ckg.addNode("dep:" + ga, "Dependency", attrs);
            }
        }

        // File + Class + Method
        if (java != null && java.compilationUnits() != null) {
            java.compilationUnits().forEach(cu -> {
                String filePath = cu.getStorage().map(s -> s.getPath().toString()).orElse("unknown");
                CkgNode fileNode = ckg.addNode("file:" + filePath, "File",
                    Map.of("path", filePath));

                cu.findAll(com.github.javaparser.ast.body.ClassOrInterfaceDeclaration.class).forEach(c -> {
                    String fqn = c.getFullyQualifiedName().orElse(c.getNameAsString());
                    CkgNode classNode = ckg.addNode("class:" + fqn, "Class",
                        Map.of("name", c.getNameAsString(), "fqn", fqn));
                    ckg.addEdge(fileNode, classNode, "DECLARES");

                    c.getMethods().forEach(m -> {
                        String mid = fqn + "#" + m.getNameAsString() + "(" + m.getParameters().size() + ")";
                        CkgNode methodNode = ckg.addNode("method:" + mid, "Method",
                            Map.of("name", m.getNameAsString(), "owner", fqn));
                        ckg.addEdge(classNode, methodNode, "CONTAINS");
                    });
                });
            });
        }

        // SQL (with dialect annotation)
        Map<String, String> dialectIndex = new HashMap<>();
        if (dialect != null && dialect.items() != null) {
            dialect.items().forEach(it -> dialectIndex.put(it.raw().text(), it.dialect()));
        }
        if (sql != null && sql.sqls() != null) {
            int i = 0;
            for (SqlResult.RawSql r : sql.sqls()) {
                String sid = "sql:" + (++i);
                Map<String, Object> attrs = new HashMap<>();
                attrs.put("text", r.text().length() > 200 ? r.text().substring(0, 200) + "..." : r.text());
                attrs.put("origin", r.origin());
                attrs.put("line", r.line());
                attrs.put("kind", r.kind());
                attrs.put("dynamic", r.dynamic());
                attrs.put("dialect", dialectIndex.getOrDefault(r.text(), "GENERIC"));
                CkgNode sqlNode = ckg.addNode(sid, "SQL", attrs);
                CkgNode owner = ckg.getById("file:" + r.origin());
                if (owner != null) ckg.addEdge(owner, sqlNode, "REFERS_TO");
            }
        }

        // ConfigKey
        if (cfg != null && cfg.keys() != null) {
            for (ConfigResult.Key k : cfg.keys()) {
                String kid = "cfg:" + k.file() + ":" + k.key();
                Map<String, Object> attrs = new HashMap<>();
                attrs.put("file", k.file());
                attrs.put("key", k.key());
                attrs.put("sensitive", k.sensitive());
                attrs.put("encrypted", k.encrypted());
                ckg.addNode(kid, "ConfigKey", attrs);
            }
        }

        return ckg;
    }

    /** 空库子，服务层可用于单元测试或未调用 analyzer 时的默认返回。 */
    public Ckg empty() { return new Ckg(); }

    /** 快捷重载，免得每个入口都要传 5 个参数。 */
    public Ckg build(PomResult pom, JavaResult java, SqlResult sql, DialectResult dialect) {
        return build(pom, java, sql, dialect, null);
    }

    /** 作为总入口供业务使用 (kindHistogram 输出可用于仪表盘)。 */
    public List<String> summary(Ckg ckg) {
        return ckg.kindHistogram().entrySet().stream()
            .map(e -> e.getKey() + "=" + e.getValue())
            .toList();
    }
}
