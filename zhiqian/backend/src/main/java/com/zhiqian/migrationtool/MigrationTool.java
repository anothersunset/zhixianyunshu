package com.zhiqian.migrationtool;

import java.util.List;
import java.util.Map;

/**
 * v2-step-22: 迁移工具抽象。
 * ZhiQian 不是唯一选型: pgloader (社区) / MTK (Microsoft Toolkit) 都是业界成熟实现,
 * 适配层让用户根据场景选择, ZhiQian 作为 smart fallback (复杂转译 + RAG 增强)。
 */
public interface MigrationTool {
    /** 唯一标识: zhiqian-native / pgloader / mtk-mysql-pg / mtk-ora-pg 等 */
    String id();
    String displayName();
    String description();
    /** 支持的源方言 (mysql, oracle, sqlserver, postgres, opengauss…) */
    List<String> supportedSources();
    /** 支持的目标方言 */
    List<String> supportedTargets();
    /** 使用代价 / 限制 / 适用场景, 给前端画对比卡 */
    Map<String, Object> tradeoffs();
    /**
     * 是否能处理 source→target 迁移。返 score 0.0−1.0,
     * MigrationToolFactory 取 max score 推荐。
     */
    double matchScore(String sourceDialect, String targetDialect);
}
