package com.zhiqian.ckg.model;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public final class CkgNode {
    private final String id;
    private final String kind;
    private final Map<String, Object> attrs;

    public CkgNode(String id, String kind, Map<String, Object> attrs) {
        this.id = id;
        this.kind = kind;
        this.attrs = attrs == null ? new HashMap<>() : new HashMap<>(attrs);
    }

    public String id() { return id; }
    public String kind() { return kind; }
    public Map<String, Object> attrs() { return attrs; }

    public Object attr(String key) { return attrs.get(key); }
    public CkgNode setAttr(String key, Object value) { attrs.put(key, value); return this; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof CkgNode n)) return false;
        return Objects.equals(id, n.id);
    }
    @Override
    public int hashCode() { return Objects.hash(id); }

    @Override public String toString() { return kind + "(" + id + ")"; }
}
