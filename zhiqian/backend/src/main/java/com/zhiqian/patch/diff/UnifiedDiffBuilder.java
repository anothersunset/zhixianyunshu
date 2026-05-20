package com.zhiqian.patch.diff;

public final class UnifiedDiffBuilder {
    private UnifiedDiffBuilder() {}

    public static String build(String file, String oldStr, String newStr) {
        String[] o = oldStr.split("\n", -1);
        String[] n = newStr.split("\n", -1);
        StringBuilder sb = new StringBuilder();
        sb.append("--- a/").append(file).append('\n');
        sb.append("+++ b/").append(file).append('\n');
        sb.append("@@ -1,").append(o.length).append(" +1,").append(n.length).append(" @@\n");
        for (String l : o) sb.append('-').append(l).append('\n');
        for (String l : n) sb.append('+').append(l).append('\n');
        return sb.toString();
    }
}
