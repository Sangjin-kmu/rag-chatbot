package com.kdd.security;

import com.kdd.config.AppConfig;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class JwtService {

    private final AppConfig appConfig;

    private SecretKey getKey() {
        byte[] keyBytes = appConfig.getJwtSecret().getBytes(StandardCharsets.UTF_8);
        if (keyBytes.length < 32) {
            byte[] padded = new byte[32];
            System.arraycopy(keyBytes, 0, padded, 0, keyBytes.length);
            return Keys.hmacShaKeyFor(padded);
        }
        return Keys.hmacShaKeyFor(keyBytes);
    }

    public String createToken(String email, String name) {
        return Jwts.builder()
                .claim("email", email)
                .claim("name", name)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + 7 * 24 * 3600 * 1000L))
                .signWith(getKey())
                .compact();
    }

    public Map<String, String> parseToken(String token) {
        Claims claims = Jwts.parser()
                .verifyWith(getKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
        return Map.of(
                "email", claims.get("email", String.class),
                "name", claims.get("name", String.class)
        );
    }

    public String extractEmail(String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) return null;
        try {
            Map<String, String> claims = parseToken(authHeader.substring(7));
            return claims.get("email");
        } catch (Exception e) {
            return null;
        }
    }
}
