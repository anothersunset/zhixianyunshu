FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /workspace
COPY settings.xml /root/.m2/settings.xml
COPY pom.xml .
RUN mvn -B -q -DskipTests dependency:go-offline || true
COPY src ./src
RUN mvn -B -q -Dmaven.test.skip=true package

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
# curl 供 HEALTHCHECK 命中 actuator/health（该端点 permitAll）；
# python3 + sqlglot 供 SqlSyntaxValidator 的确定性 critic 校验（版本与 eval/ 侧锁定一致）。
RUN apt-get update && apt-get install -y --no-install-recommends curl python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir sqlglot==25.16.1
COPY --from=build /workspace/target/*.jar app.jar
# SqlSyntaxValidator 以 CWD 相对路径 ../../eval/sql_validate.py 定位脚本，
# WORKDIR=/app 时解析为 /eval/sql_validate.py —— 由仓库 eval/ 构建上下文直接提供
# （compose 的 additional_contexts: eval_src），无副本、无漂移。
COPY --from=eval_src sql_validate.py /eval/sql_validate.py
# 非 root 运行
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
