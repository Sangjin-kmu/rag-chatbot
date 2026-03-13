package com.kdd.dto;

import lombok.Data;

@Data
public class ProfileRequest {
    private String name;
    private String studentId;
    private String department;
    private String grade;
}
