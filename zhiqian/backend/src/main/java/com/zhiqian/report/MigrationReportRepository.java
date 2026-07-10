package com.zhiqian.report;

import org.springframework.data.repository.CrudRepository;

import java.util.Optional;

public interface MigrationReportRepository extends CrudRepository<MigrationReport, Long> {
    Optional<MigrationReport> findFirstByTaskIdOrderByIdDesc(Long taskId);
}
