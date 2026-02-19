# eidosSpeech v2 - User Acceptance Test (UAT) Checklist

## 1. Authentication & User Journey
- [ ] **M2.1 Register**
  - [ ] Valid data -> Success (Check console logs or email inbox for token link).
  - [ ] Duplicate email -> Error 409 Conflict.
  - [ ] Weak password -> Error 400.
- [ ] **M2.2 Verify Email**
  - [ ] Use token from log/email -> Success 200.
  - [ ] Receive API Key & Auto Login.
- [ ] **M2.3 Login**
  - [ ] Valid credentials -> Success 200 (Access Token received).
  - [ ] Invalid password -> Error 401.
- [ ] **M2.4 Protected Routes**
  - [ ] Access `/api/v1/auth/me` with token -> Success 200.
  - [ ] Access `/api/v1/auth/me` without token -> Error 401.

## 2. Core Features (TTS)
- [ ] **M5.1 Anonymous TTS**
  - [ ] Open incognito window (Landing Page).
  - [ ] Generate TTS -> Success.
  - [ ] Check Response Header `X-RateLimit-Tier: anonymous`.
- [ ] **M5.2 Registered TTS**
  - [ ] Use API Key from Dashboard.
  - [ ] Generate TTS via curl/python -> Success.
  - [ ] Check Response Header `X-RateLimit-Tier: registered`.
- [ ] **M5.3 Caching**
  - [ ] Request same text/voice twice.
  - [ ] Second request `X-Cache-Hit: true`.

## 3. Rate Limiting
- [ ] **M4.1 Daily Limit**
  - [ ] Exceed daily limit (anonymous: 5, registered: 30).
  - [ ] Verify HTTP 429 Too Many Requests.
  - [ ] Verify `Retry-After` header present.
- [ ] **M4.2 Concurrent Requests**
  - [ ] Send 2 requests simultaneously (e.g. from 2 tabs).
  - [ ] One might fail with 429 or handle sequentially if semaphore works.

## 4. Admin Panel
- [ ]Access `/admin`.
- [ ] Enter `ADMIN_KEY` from `.env`.
- [ ] Verify Dashboard stats (Users, Requests).
- [ ] Ban a test user.
- [ ] Try logging in with Banned User -> Fail.

## 5. Security Sanity Check
- [ ] **M9.1 SQL Injection**
  - [ ] Try searching user with `' OR 1=1 --`.
  - [ ] Should not return all users.
- [ ] **M9.2 XSS**
  - [ ] Input TTS Text `<script>alert(1)</script>`.
  - [ ] Should return Audio, not execute script.

---
**Test Result Summary:**
| Test Case | Status | Notes |
|-----------|--------|-------|
| Auth      | [ ]    |       |
| TTS       | [ ]    |       |
| RateLimit | [ ]    |       |
| Admin     | [ ]    |       |
