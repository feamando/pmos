# AI Brain Tools

Tools designed to interact with the Semantic Knowledge Graph (`AI_Guidance/Brain`).

## Scripts

### `search-brain.ps1`
A focused search tool for the Brain. It searches Markdown files within `AI_Guidance/Brain`.

**Usage:**
```powershell
# Search everything for "OTP"
.\search-brain.ps1 "OTP"

# Search only Projects for "Good Chop"
.\search-brain.ps1 -Query "Good Chop" -Category "Projects"

# Search with more context
.\search-brain.ps1 "budget" -Context 5
```

**Why use this over `grep`?**
*   It defaults to the correct directory (`../Brain`).
*   It formats output specifically for LLM readability (File path, Context lines).
*   It filters for `.md` files automatically.
