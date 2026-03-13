package com.kdd;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class KddApplication {
    public static void main(String[] args) {
        SpringApplication.run(KddApplication.class, args);
    }
}
