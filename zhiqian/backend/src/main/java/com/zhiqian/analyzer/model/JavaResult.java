package com.zhiqian.analyzer.model;
import com.github.javaparser.ast.CompilationUnit;
import java.util.List;
public record JavaResult(List<CompilationUnit> compilationUnits) {}
