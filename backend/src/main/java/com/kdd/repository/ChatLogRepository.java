package com.kdd.repository;

import com.kdd.entity.ChatLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.time.LocalDateTime;
import java.util.List;

public interface ChatLogRepository extends JpaRepository<ChatLog, Long> {

    long count();

    long countByCreatedAtAfter(LocalDateTime after);

    @Query("SELECT c.question, c.answer, c.sources, COUNT(c) as cnt FROM ChatLog c " +
           "WHERE c.createdAt >= :since GROUP BY c.question ORDER BY cnt DESC")
    List<Object[]> findFrequentQuestions(@Param("since") LocalDateTime since);

    @Query("SELECT FUNCTION('date', c.createdAt) as d, COUNT(c) FROM ChatLog c " +
           "WHERE c.createdAt >= :since GROUP BY d ORDER BY d")
    List<Object[]> findDailyStats(@Param("since") LocalDateTime since);

    @Query("SELECT FUNCTION('strftime', '%H', c.createdAt) as h, COUNT(c) FROM ChatLog c GROUP BY h ORDER BY h")
    List<Object[]> findHourlyStats();

    @Query("SELECT c.sources FROM ChatLog c WHERE c.createdAt >= :since AND c.sources IS NOT NULL")
    List<String> findSourcesSince(@Param("since") LocalDateTime since);
}
