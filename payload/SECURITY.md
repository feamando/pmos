# Security Guide for PM-OS

This document outlines security best practices and configuration requirements for the PM-OS system.

## 🔐 Security Principles

1. **Zero Trust**: Never trust hardcoded credentials in the repository
2. **Least Privilege**: Grant minimum required permissions to API keys
3. **Defense in Depth**: Use multiple layers of security protection
4. **Regular Rotation**: Rotate credentials periodically

## 🚨 Security Alerts

### Compromised Credentials Found (Now Fixed)

**URGENT ACTION REQUIRED**: Hardcoded credentials were found in the repository and have been removed:

1. **Jira API Token** (File: `AI_Guidance/Tools/jira_mcp/config.json`)
   - Account: `nikita.gorshkov@hellofresh.com`
   - Token: `[REDACTED - COMPROMISED]`
   - **ACTION**: This token must be rotated immediately in Atlassian

2. **Google API Key** (File: `AI_Guidance/Tools/meeting_prep/config.json`)
   - Key: `[REDACTED - COMPROMISED]`
   - **ACTION**: This key must be rotated immediately in Google Cloud Console

## 🛡️ Security Configuration

### API Key Management

#### Google API Keys

**Required APIs:**
- Google Drive API
- Gmail API  
- Google Calendar API
- Gemini API (for AI features)

**Recommended Scopes:**
```
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/calendar.readonly
```

**Configuration File:**
```json
{
  "google_api_key": "YOUR_API_KEY_HERE",
  "gemini_model": "gemini-2.5-flash"
}
```

#### Jira API Tokens

**Configuration File:**
```json
{
  "url": "https://your-domain.atlassian.net/",
  "username": "your-email@domain.com",
  "api_token": "YOUR_API_TOKEN_HERE"
}
```

### Environment Variables (Recommended)

```bash
# Google API
export GOOGLE_API_KEY="your_google_api_key"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# Jira API
export JIRA_API_TOKEN="your_jira_api_token"
export JIRA_BASE_URL="https://your-domain.atlassian.net"

# Gemini API
export GEMINI_API_KEY="your_gemini_api_key"
```

## 📁 File Protection

### .gitignore Rules

The following files are protected from accidental commits:

```gitignore
# API Configuration Files
AI_Guidance/Tools/jira_mcp/config.json
AI_Guidance/Tools/meeting_prep/config.json

# OAuth Tokens
AI_Guidance/Tools/gdrive_mcp/token.json
AI_Guidance/Tools/daily_context/token.json

# Credentials
*.pem
*.key
*.secret
credentials.json
```

### File Permissions

```bash
# Restrict access to sensitive files
chmod 600 AI_Guidance/Tools/*/config.json
chmod 600 AI_Guidance/Tools/*/token.json
```

## 🔧 Security Best Practices

### For Developers

1. **Never hardcode credentials** - Use environment variables or secure config files
2. **Use .env files** for local development (add .env to .gitignore)
3. **Validate inputs** - Sanitize all user inputs and API responses
4. **Implement rate limiting** - Prevent API abuse
5. **Use HTTPS** - Never transmit sensitive data over HTTP

### For Users

1. **Rotate credentials regularly** - Every 90 days minimum
2. **Monitor API usage** - Set up alerts for unusual activity
3. **Limit IP ranges** - Restrict API key usage to known IPs
4. **Use separate accounts** - Don't use personal accounts for system integration
5. **Review permissions** - Audit API key permissions quarterly

## 🚨 Incident Response

### If You Accidentally Commit Credentials

1. **Immediately rotate** the compromised credentials
2. **Remove from Git history**:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch AI_Guidance/Tools/*/config.json" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Push the cleaned history**:
   ```bash
   git push origin --force --all
   git push origin --force --tags
   ```
4. **Notify team members** to update their local repositories

### If You Suspect a Breach

1. **Rotate all credentials** immediately
2. **Review API logs** for unauthorized access
3. **Check system integrity** - Look for unauthorized changes
4. **Notify stakeholders** according to your security policy

## 🔄 Credential Rotation Procedure

### Google API Keys

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to "APIs & Services" > "Credentials"
3. Select the key and click "Regenerate"
4. Update all configuration files with the new key
5. Restart all services using the key

### Jira API Tokens

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Revoke the compromised token
3. Create a new token
4. Update the configuration file
5. Restart the Jira MCP service

## 📚 Additional Resources

- [Google Cloud Security Best Practices](https://cloud.google.com/security/best-practices)
- [Atlassian Security Guidelines](https://www.atlassian.com/trust/security)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)

## 🛑 Security Checklist

- [ ] All API keys removed from version control
- [ ] Config files added to .gitignore
- [ ] Environment variable support implemented
- [ ] Credential rotation procedure documented
- [ ] Incident response plan in place
- [ ] Regular security audits scheduled

**Last Security Audit**: 2025-12-10
**Next Audit Due**: 2026-03-10