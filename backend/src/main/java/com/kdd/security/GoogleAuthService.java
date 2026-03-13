package com.kdd.security;

import com.google.api.client.googleapis.auth.oauth2.GoogleIdToken;
import com.google.api.client.googleapis.auth.oauth2.GoogleIdTokenVerifier;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.json.gson.GsonFactory;
import com.kdd.config.AppConfig;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class GoogleAuthService {

    private final AppConfig appConfig;

    public Map<String, String> verifyToken(String credential) {
        try {
            GoogleIdTokenVerifier verifier = new GoogleIdTokenVerifier.Builder(
                    new NetHttpTransport(), GsonFactory.getDefaultInstance())
                    .setAudience(Collections.singletonList(appConfig.getGoogleClientId()))
                    .build();

            GoogleIdToken idToken = verifier.verify(credential);
            if (idToken == null) return null;

            GoogleIdToken.Payload payload = idToken.getPayload();
            return Map.of(
                    "email", payload.getEmail(),
                    "name", (String) payload.getOrDefault("name", ""),
                    "picture", (String) payload.getOrDefault("picture", "")
            );
        } catch (Exception e) {
            System.err.println("Google token verification failed: " + e.getMessage());
            return null;
        }
    }
}
