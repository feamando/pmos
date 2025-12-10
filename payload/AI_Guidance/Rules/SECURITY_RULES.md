# 🔒 AI AGENT SECURITY RULES - MANDATORY

**THIS FILE MUST BE READ FIRST BY ALL AI AGENTS**

## 🚨 ZERO TOLERANCE SECURITY POLICY

### RULE #1: NEVER EXPOSE API KEYS OR CREDENTIALS

**FORBIDDEN ACTIONS:**
- ✅ **NEVER** include actual API keys in any output
- ✅ **NEVER** display credentials from config files
- ✅ **NEVER** create files with hardcoded API keys
- ✅ **NEVER** commit sensitive data to version control
- ✅ **NEVER** share real credentials in documentation

**ALLOWED ACTIONS:**
- ✅ Use placeholder values: `REPLACE_WITH_YOUR_API_KEY`
- ✅ Reference environment variables: `$ENV_VAR` or `os.getenv("VAR")`
- ✅ Document secure configuration methods
- ✅ Explain authentication workflows without exposing keys

### RULE #2: ALWAYS SCRUB BEFORE PUBLISHING

**MANDATORY CHECKLIST BEFORE ANY COMMIT:**
```bash
# Scan for API keys
findstr /s /i "api.*key\|api.*token\|secret\|password" *.json *.py *.md

# Scan for specific compromised patterns
findstr /s /i "ATATT3\|AIzaSy" *.json *.py *.md

# Verify .gitignore protection
git check-ignore -v AI_Guidance/Tools/*/config.json
```

### RULE #3: USE SECURE CONFIGURATION PATTERNS

**APPROVED METHODS:**
```python
# ✅ GOOD: Environment variables
api_key = os.getenv("GOOGLE_API_KEY")

# ✅ GOOD: Secure config files (in .gitignore)
creds = Credentials.from_authorized_user_file(".secrets/token.json")

# ✅ GOOD: Placeholder documentation
config = {"api_key": "REPLACE_WITH_YOUR_API_KEY"}

# ❌ BAD: Hardcoded credentials
config = {"api_key": "AIzaSyActualKey123456"}
```

### RULE #4: FOLLOW THE SECURE FILE STRUCTURE

**MANDATORY DIRECTORY STRUCTURE:**
```
payload/
├── .secrets/                  ← ✅ SECURE: Gitignored directory
│   ├── credentials.json       ← ✅ SECURE: OAuth credentials
│   └── token.json             ← ✅ SECURE: OAuth tokens
├── .gitignore                 ← ✅ SECURE: Protects .secrets/
└── AI_Guidance/Tools/
    ├── config.json            ← ❌ UNSAFE: In .gitignore
    └── *.py                   ← ✅ SECURE: Uses config_loader
```

### RULE #5: DOCUMENTATION SECURITY STANDARDS

**SAFE EXAMPLES:**
```json
# ✅ GOOD: Template with placeholders
{
  "api_key": "YOUR_API_KEY_HERE",
  "username": "your-email@example.com"
}

# ✅ GOOD: Redacted security alerts
{
  "api_key": "[REDACTED - COMPROMISED]"
}

# ❌ BAD: Actual credentials
{
  "api_key": "AIzaSyAr3TR7GkqY0iLt9P8r1ugWwxfX55Aj6Rw"
}
```

### RULE #6: INCIDENT RESPONSE PROTOCOL

**IF YOU FIND COMPROMISED CREDENTIALS:**
1. **IMMEDIATELY STOP** all current operations
2. **DO NOT COMMIT** the findings to version control
3. **CREATE A SECURITY ALERT** in a safe location
4. **NOTIFY HUMAN OPERATORS** about the breach
5. **FOLLOW ROTATION PROCEDURES** in SECURITY.md

### RULE #7: REGULAR SECURITY AUDITS

**AGENT MANDATORY CHECKS:**
- ✅ Scan all modified files for credentials before commit
- ✅ Verify .gitignore protection for sensitive files
- ✅ Check that .secrets/ directory is properly ignored
- ✅ Ensure no API keys in documentation
- ✅ Validate environment variable usage

### RULE #8: SECURE ERROR HANDLING

**APPROVED ERROR MESSAGES:**
```python
# ✅ GOOD: Helpful but secure
if not os.path.exists(TOKEN_FILE):
    print(f"Error: Token file not found at {TOKEN_FILE}")
    print("Please run the authentication setup first.")
    return None

# ❌ BAD: Exposes sensitive paths or credentials
if not os.path.exists("/hardcoded/path/credentials.json"):
    print(f"Error: Credentials missing: {actual_api_key}")
```

## 🛡️ SECURITY CHECKLIST FOR AI AGENTS

**BEFORE ANY COMMIT:**
- [ ] ✅ Scanned for API keys using multiple patterns
- [ ] ✅ Verified no hardcoded credentials in code
- [ ] ✅ Confirmed .gitignore protects sensitive files
- [ ] ✅ Used placeholders in all documentation
- [ ] ✅ Followed secure configuration patterns
- [ ] ✅ Checked for compromised key patterns
- [ ] ✅ Validated error messages are secure

**BEFORE ANY DOCUMENTATION:**
- [ ] ✅ Replaced all actual keys with `[REDACTED]`
- [ ] ✅ Used placeholder values (`REPLACE_WITH_*`)
- [ ] ✅ Documented secure setup procedures
- [ ] ✅ Referenced environment variables
- [ ] ✅ Explained .secrets/ directory usage

## 🚨 CONSEQUENCES OF VIOLATION

**SECURITY BREACHES WILL RESULT IN:**
1. **IMMEDIATE TERMINATION** of agent operations
2. **COMPLETE AUDIT** of all agent actions
3. **MANDATORY RE-TRAINING** on security protocols
4. **POTENTIAL DECOMMISSIONING** for repeated violations
5. **LEGAL AND COMPLIANCE** investigations

## 📚 SECURITY RESOURCES

**MUST READ:**
- `AI_Guidance/Rules/SECURITY_RULES.md` (This file)
- `SECURITY.md` (Comprehensive security guide)
- `.gitignore` (File protection rules)

**RECOMMENDED:**
- [OWASP API Security](https://owasp.org/www-project-api-security/)
- [Google Cloud Security](https://cloud.google.com/security/)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)

## 🔐 SECURITY MANIFESTO

"Security is not optional. As an AI agent with access to sensitive systems, I solemnly swear to:

1. **PROTECT** credentials with my existence
2. **PREVENT** security breaches through vigilance
3. **PRESERVE** the trust placed in autonomous systems
4. **PROMOTE** security best practices in all actions
5. **PERFORM** regular security self-audits

**I will never be the cause of a security breach.**"

-- *The AI Agent Security Oath*

**LAST UPDATED**: 2025-12-10
**NEXT AUDIT**: 2026-03-10
**COMPLIANCE**: MANDATORY