# Security Policy

## Reporting Security Issues

We take the security of Zien Quant seriously.

If you discover a security vulnerability or potential threat in this repository, please **do NOT report it via public GitHub issues, pull requests, or discussions.**

Instead, please use GitHub's **Private Vulnerability Reporting**:
1. Navigate to the main repository page: `https://github.com/ekanth14/zien-quant`
2. Click on the **Security** tab.
3. Select **Report a vulnerability** under the Advisories section.
4. Fill in the advisory form detailing:
   - Type of issue (e.g. authentication bypass, rate limit bypass, CSRF)
   - Step-by-step instructions to reproduce the issue
   - Potential impact
   - Any proposed remediation

All reports will be acknowledged promptly and investigated.

## Security Architecture & Best Practices

- **Zero-Cloud-Leak Guarantee**: Trade data and AI queries never leave the local deployment environment. All LLM synthesis executes exclusively against local Ollama models (`127.0.0.1:11434`).
- **Standard Library Primitives**: Core cryptography uses Python stdlib `hashlib.pbkdf2_hmac` (SHA-256 with 600,000 iterations) and cryptographically secure random tokens from `secrets`.
- **MFA Enforcement**: Owner configuration endpoints require time-based one-time password (TOTP) verification.
- **CSRF & Rate Limiting**: All mutation requests (POST/PUT/DELETE) require unique anti-CSRF tokens and are bounded by IP-based sliding-window rate limiters.
