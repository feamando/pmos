"""
LLM Provider Step

Configure the LLM provider for PM-OS.
"""

import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


LLM_PROVIDERS = {
    "bedrock": {
        "name": "AWS Bedrock",
        "description": "Claude via AWS Bedrock (recommended for enterprise)",
        "env_vars": ["AWS_REGION", "AWS_DEFAULT_REGION"],
        "model_default": "anthropic.claude-3-5-sonnet-20241022-v2:0"
    },
    "anthropic": {
        "name": "Anthropic API",
        "description": "Direct Anthropic API (requires API key)",
        "env_vars": ["ANTHROPIC_API_KEY"],
        "model_default": "claude-sonnet-4-20250514"
    },
    "openai": {
        "name": "OpenAI API",
        "description": "OpenAI GPT models",
        "env_vars": ["OPENAI_API_KEY"],
        "model_default": "gpt-4-turbo"
    },
    "ollama": {
        "name": "Ollama (Local)",
        "description": "Local LLM via Ollama (free, private)",
        "env_vars": ["OLLAMA_HOST"],
        "model_default": "llama3.1"
    }
}


def check_existing_credentials(provider: str) -> Optional[str]:
    """Check if credentials already exist for a provider."""
    config = LLM_PROVIDERS.get(provider, {})
    env_vars = config.get("env_vars", [])

    for var in env_vars:
        if os.environ.get(var):
            return var
    return None


def llm_provider_step(wizard: "WizardOrchestrator") -> bool:
    """Configure LLM provider.

    Returns:
        True to continue, False to abort
    """
    # Quick mode: auto-detect best available provider
    if wizard.quick_mode:
        return _quick_llm_provider_step(wizard)

    wizard.console.print("[bold]Configure your LLM provider.[/bold]")
    wizard.console.print("[dim]PM-OS uses AI to generate documents and assist with PM tasks.[/dim]")
    wizard.console.print()

    # Check prerequisites for Bedrock
    prereqs = wizard.get_data("prerequisites", {})
    bedrock_available = prereqs.get("Bedrock Access", {}).get("passed", False)

    # Build choices with keys for reliable lookup
    provider_keys = list(LLM_PROVIDERS.keys())
    choices = []
    choice_to_key = {}  # Map display name to provider key

    for key, config in LLM_PROVIDERS.items():
        name = config["name"]
        display_name = name  # Base display name without decorations
        if key == "bedrock" and not bedrock_available:
            display_name += " [dim](not configured)[/dim]"
        elif check_existing_credentials(key):
            display_name += " [green](credentials found)[/green]"
        choices.append(display_name)
        # Store mapping from both decorated and base name
        choice_to_key[display_name] = key
        choice_to_key[name] = key

    # Get existing selection
    existing = wizard.get_data("llm_provider", "")
    default_choice = None
    if existing and existing in provider_keys:
        idx = provider_keys.index(existing)
        default_choice = choices[idx]

    # Default to Bedrock if available, otherwise Anthropic
    if not default_choice:
        default_choice = choices[0] if bedrock_available else choices[1]

    # Select provider
    selected = wizard.ui.prompt_choice(
        "Select your LLM provider",
        choices=choices,
        default=default_choice
    )

    # Map back to provider key using the mapping (robust lookup)
    provider_key = choice_to_key.get(selected)
    if not provider_key:
        # Fallback: try to find by index
        try:
            idx = choices.index(selected)
            provider_key = provider_keys[idx]
        except (ValueError, IndexError):
            provider_key = "anthropic"  # Safe default

    provider_config = LLM_PROVIDERS[provider_key]

    wizard.console.print()

    # Configure based on provider
    if provider_key == "bedrock":
        return configure_bedrock(wizard, provider_config)
    elif provider_key == "anthropic":
        return configure_anthropic(wizard, provider_config)
    elif provider_key == "openai":
        return configure_openai(wizard, provider_config)
    elif provider_key == "ollama":
        return configure_ollama(wizard, provider_config)

    return True


def configure_bedrock(wizard: "WizardOrchestrator", config: dict) -> bool:
    """Configure AWS Bedrock."""
    wizard.console.print("[bold]AWS Bedrock Configuration[/bold]")
    wizard.console.print()

    # Check for existing AWS configuration
    existing_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

    if existing_region:
        wizard.ui.print_success(f"AWS region detected: {existing_region}")

    region = wizard.ui.prompt_text(
        "AWS Region for Bedrock",
        default=existing_region or "us-east-1"
    )

    model = wizard.ui.prompt_text(
        "Bedrock model ID",
        default=wizard.get_data("llm_model") or config["model_default"]
    )

    wizard.update_data({
        "llm_provider": "bedrock",
        "llm_model": model,
        "aws_region": region
    })

    wizard.ui.print_success("Bedrock configured!")
    return True


def configure_anthropic(wizard: "WizardOrchestrator", config: dict) -> bool:
    """Configure Anthropic API."""
    wizard.console.print("[bold]Anthropic API Configuration[/bold]")
    wizard.console.print()

    existing_key = os.environ.get("ANTHROPIC_API_KEY")

    if existing_key:
        wizard.ui.print_success("Anthropic API key found in environment")
        use_existing = wizard.ui.prompt_confirm("Use existing API key?", default=True)
        if use_existing:
            api_key = existing_key
        else:
            api_key = wizard.ui.prompt_password("Anthropic API key", required=True)
    else:
        wizard.console.print("[dim]Get your API key at: https://console.anthropic.com/[/dim]")
        api_key = wizard.ui.prompt_password("Anthropic API key", required=True)

    # Test credentials inline
    wizard.console.print()
    wizard.console.print("[dim]Testing credentials...[/dim]")
    try:
        from pm_os.wizard.credential_testers import test_anthropic_credentials
        success, message = test_anthropic_credentials.__wrapped__(api_key=api_key)
        if success:
            wizard.ui.print_success(message)
        else:
            wizard.ui.print_warning(f"Credential test: {message}")
            if not wizard.ui.prompt_confirm("Continue anyway?", default=False):
                return configure_anthropic(wizard, config)  # Retry
    except Exception as e:
        wizard.ui.print_warning(f"Could not test credentials: {e}")

    model = wizard.ui.prompt_text(
        "Model name",
        default=wizard.get_data("llm_model") or config["model_default"]
    )

    wizard.update_data({
        "llm_provider": "anthropic",
        "llm_model": model,
        "anthropic_api_key": api_key
    })

    wizard.ui.print_success("Anthropic API configured!")
    return True


def configure_openai(wizard: "WizardOrchestrator", config: dict) -> bool:
    """Configure OpenAI API."""
    wizard.console.print("[bold]OpenAI API Configuration[/bold]")
    wizard.console.print()

    existing_key = os.environ.get("OPENAI_API_KEY")

    if existing_key:
        wizard.ui.print_success("OpenAI API key found in environment")
        use_existing = wizard.ui.prompt_confirm("Use existing API key?", default=True)
        if use_existing:
            api_key = existing_key
        else:
            api_key = wizard.ui.prompt_password("OpenAI API key", required=True)
    else:
        wizard.console.print("[dim]Get your API key at: https://platform.openai.com/[/dim]")
        api_key = wizard.ui.prompt_password("OpenAI API key", required=True)

    # Test credentials inline
    wizard.console.print()
    wizard.console.print("[dim]Testing credentials...[/dim]")
    try:
        from pm_os.wizard.credential_testers import test_openai_credentials
        success, message = test_openai_credentials.__wrapped__(api_key=api_key)
        if success:
            wizard.ui.print_success(message)
        else:
            wizard.ui.print_warning(f"Credential test: {message}")
            if not wizard.ui.prompt_confirm("Continue anyway?", default=False):
                return configure_openai(wizard, config)  # Retry
    except Exception as e:
        wizard.ui.print_warning(f"Could not test credentials: {e}")

    model = wizard.ui.prompt_text(
        "Model name",
        default=wizard.get_data("llm_model") or config["model_default"]
    )

    wizard.update_data({
        "llm_provider": "openai",
        "llm_model": model,
        "openai_api_key": api_key
    })

    wizard.ui.print_success("OpenAI API configured!")
    return True


def configure_ollama(wizard: "WizardOrchestrator", config: dict) -> bool:
    """Configure Ollama (local)."""
    wizard.console.print("[bold]Ollama Configuration[/bold]")
    wizard.console.print()

    host = wizard.ui.prompt_text(
        "Ollama host URL",
        default=os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    )

    # Test connection inline
    wizard.console.print()
    wizard.console.print("[dim]Testing connection...[/dim]")
    try:
        from pm_os.wizard.credential_testers import test_ollama_connection
        success, message = test_ollama_connection.__wrapped__(host=host)
        if success:
            wizard.ui.print_success(message)
        else:
            wizard.ui.print_warning(f"Connection test: {message}")
            if not wizard.ui.prompt_confirm("Continue anyway?", default=True):
                return configure_ollama(wizard, config)  # Retry
    except Exception as e:
        wizard.ui.print_warning(f"Could not test connection: {e}")

    model = wizard.ui.prompt_text(
        "Model name",
        default=wizard.get_data("llm_model") or config["model_default"]
    )

    wizard.update_data({
        "llm_provider": "ollama",
        "llm_model": model,
        "ollama_host": host
    })

    wizard.ui.print_success("Ollama configured!")
    wizard.console.print()
    wizard.ui.print_info("Make sure Ollama is running before using PM-OS.")
    return True


def _quick_llm_provider_step(wizard: "WizardOrchestrator") -> bool:
    """Quick mode: auto-detect best available LLM provider without prompting."""
    wizard.console.print("[bold]Quick LLM Setup[/bold]")
    wizard.console.print("[dim]Auto-detecting LLM provider...[/dim]")

    prereqs = wizard.get_data("prerequisites", {})
    bedrock_available = prereqs.get("Bedrock Access", {}).get("passed", False)

    # Priority: Bedrock > Anthropic > OpenAI > default to Anthropic
    if bedrock_available:
        provider = "bedrock"
        model = LLM_PROVIDERS["bedrock"]["model_default"]
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        wizard.update_data({
            "llm_provider": provider,
            "llm_model": model,
            "aws_region": region,
        })
        wizard.ui.print_success(f"Auto-selected: AWS Bedrock ({model})")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        provider = "anthropic"
        model = LLM_PROVIDERS["anthropic"]["model_default"]
        wizard.update_data({
            "llm_provider": provider,
            "llm_model": model,
            "anthropic_api_key": os.environ["ANTHROPIC_API_KEY"],
        })
        wizard.ui.print_success(f"Auto-selected: Anthropic ({model})")
    elif os.environ.get("OPENAI_API_KEY"):
        provider = "openai"
        model = LLM_PROVIDERS["openai"]["model_default"]
        wizard.update_data({
            "llm_provider": provider,
            "llm_model": model,
            "openai_api_key": os.environ["OPENAI_API_KEY"],
        })
        wizard.ui.print_success(f"Auto-selected: OpenAI ({model})")
    else:
        # Default to Anthropic with no key - user will configure later
        provider = "anthropic"
        model = LLM_PROVIDERS["anthropic"]["model_default"]
        wizard.update_data({
            "llm_provider": provider,
            "llm_model": model,
        })
        wizard.ui.print_success(f"Defaulted to: Anthropic ({model})")
        wizard.console.print("[dim]Set ANTHROPIC_API_KEY in .env to enable AI features.[/dim]")

    return True
