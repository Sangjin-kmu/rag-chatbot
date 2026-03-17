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

    @Query(value = "SELECT date(created_at) as d, COUNT(*) FROM chat_logs " +
           "WHERE created_at >= :since GROUP BY d ORDER BY d",
           nativeQuery = true)
    List<Object[]> findDailyStats(@Param("since") LocalDateTime since);

    @Query(value = "SELECT strftime('%H', created_at) as h, COUNT(*) FROM chat_logs GROUP BY h ORDER BY h",
           nativeQuery = true)
    List<Object[]> findHourlyStats();

    @Query("SELECT c.sources FROM ChatLog c WHERE c.createdAt >= :since AND c.sources IS NOT NULL")
    List<String> findSourcesSince(@Param("since") LocalDateTime since);
}
