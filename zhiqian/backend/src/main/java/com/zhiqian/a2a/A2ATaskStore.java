package com.zhiqian.a2a;

import java.util.Collection;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;

@Component
public class A2ATaskStore {
    private final Map<String, A2ATask> tasks = new ConcurrentHashMap<>();

    public void save(A2ATask t) { tasks.put(t.id, t); }
    public A2ATask get(String id) { return tasks.get(id); }
    public Collection<A2ATask> all() { return tasks.values(); }
    public void clear() { tasks.clear(); }
}
