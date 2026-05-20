package com.zhiqian.suggestion;

import org.springframework.data.jdbc.repository.query.Query;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface SuggestionRepository extends CrudRepository<Suggestion, Long> {
    @Query("SELECT * FROM suggestion WHERE task_id = :tid ORDER BY id")
    List<Suggestion> findByTaskId(@Param("tid") Long tid);
}
