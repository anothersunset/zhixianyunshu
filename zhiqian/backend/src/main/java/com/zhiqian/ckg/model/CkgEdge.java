package com.zhiqian.ckg.model;

import org.jgrapht.graph.DefaultEdge;

import java.util.HashMap;
import java.util.Map;

public class CkgEdge extends DefaultEdge {
    private final String relation;
    private final Map<String, Object> attrs;

    public CkgEdge(String relation) { this(relation, null); }

    public CkgEdge(String relation, Map<String, Object> attrs) {
        this.relation = relation;
        this.attrs = attrs == null ? new HashMap<>() : new HashMap<>(attrs);
    }

    public String relation() { return relation; }
    public Map<String, Object> attrs() { return attrs; }

    @Override
    public String toString() {
        return "-[" + relation + "]->";
    }
}
