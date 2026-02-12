"""
PM-OS Wizard Steps

Individual step handlers for the installation wizard.
"""

from pm_os.wizard.steps.welcome import welcome_step
from pm_os.wizard.steps.prerequisites import prerequisites_step
from pm_os.wizard.steps.profile import profile_step
from pm_os.wizard.steps.llm_provider import llm_provider_step
from pm_os.wizard.steps.integrations import integrations_step
from pm_os.wizard.steps.directories import directories_step
from pm_os.wizard.steps.brain_population import brain_population_step
from pm_os.wizard.steps.verification import verification_step

# Step definitions for the wizard orchestrator
WIZARD_STEPS = [
    {
        "name": "welcome",
        "title": "Welcome",
        "description": "Overview of PM-OS and what will be configured",
        "handler": welcome_step,
        "skippable": False,
    },
    {
        "name": "prerequisites",
        "title": "Prerequisites",
        "description": "Check system requirements",
        "handler": prerequisites_step,
        "skippable": False,
    },
    {
        "name": "profile",
        "title": "User Profile",
        "description": "Set up your name, email, and role",
        "handler": profile_step,
        "skippable": False,
    },
    {
        "name": "llm_provider",
        "title": "LLM Provider",
        "description": "Configure your AI provider",
        "handler": llm_provider_step,
        "skippable": False,
    },
    {
        "name": "integrations",
        "title": "Integrations",
        "description": "Configure optional integrations (Jira, Slack, etc.)",
        "handler": integrations_step,
        "skippable": True,
    },
    {
        "name": "directories",
        "title": "Directory Setup",
        "description": "Create PM-OS directory structure and config files",
        "handler": directories_step,
        "skippable": False,
    },
    {
        "name": "brain_population",
        "title": "Brain Population",
        "description": "Initial sync from configured integrations",
        "handler": brain_population_step,
        "skippable": True,
    },
    {
        "name": "verification",
        "title": "Verification",
        "description": "Verify installation and show next steps",
        "handler": verification_step,
        "skippable": False,
    },
]

__all__ = [
    "welcome_step",
    "prerequisites_step",
    "profile_step",
    "llm_provider_step",
    "integrations_step",
    "directories_step",
    "brain_population_step",
    "verification_step",
    "WIZARD_STEPS",
]
