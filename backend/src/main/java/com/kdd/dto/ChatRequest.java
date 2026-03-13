package com.kdd.dto;

import lombok.Data;

@Data
public class ChatRequest {
    private String message;
    private String history = "";
}
