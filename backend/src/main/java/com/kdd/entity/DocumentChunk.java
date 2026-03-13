package com.kdd.entity;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "document_chunks")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class DocumentChunk {
    @Id
    private String id;

    @Column(columnDefinition = "TEXT")
    private String content;

    private String docName;
    private String sectionPath;
    private Integer page;
    private boolean hasTable;
    private String sourceUrl;
}
