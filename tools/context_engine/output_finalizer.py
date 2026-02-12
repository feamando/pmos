"""
Output Finalizer Module - Final Artifact Link Updates

Updates all context files with final artifact links after output generation:
1. Updates {feature}-context.md with PRD link and Jira epic link
2. Updates business-case document with approval record links and PRD reference
3. Updates ADR files with implementation status and PRD back-references
4. Ensures all cross-references are BIDIRECTIONAL:
   - Context file <-> PRD
   - Context file <-> Business Case
   - Context file <-> ADRs
   - PRD <-> Source documents (BC, ADRs, context)
   - ADRs <-> PRD (status updates + links)

This module is called as part of /generate-outputs completion to ensure
all artifacts are properly linked across the feature documentation.

Usage:
    from tools.context_engine.output_finalizer import OutputFinalizer

    finalizer = OutputFinalizer()

    # Finalize all context files after PRD generation
    result = finalizer.finalize_context_file(
        feature_path=Path("/path/to/feature"),
        prd_path=Path("/path/to/PRD.md"),
        jira_epic_url="https://atlassian.net/browse/MK-1234",
    )

    # Or update just the artifact links
    result = finalizer.update_artifact_links(
        feature_path=Path("/path/to/feature"),
        artifact_type="prd",
        artifact_path="/path/to/PRD.md"
    )

Bidirectional Link Matrix:
    +-----------------+------+----+-----+-------+------+
    | Links TO ->     | PRD  | BC | ADR | Ctx   | Jira |
    +-----------------+------+----+-----+-------+------+
    | Context File    |  Y   | Y  |  Y  |  -    |  Y   |
    | PRD             |  -   | Y  |  Y  |  Y    |  Y   |
    | Business Case   |  Y   |  - |  N  |  Y    |  N   |
    | ADRs            |  Y   | N  |  -  |  Y    |  N   |
    +-----------------+------+----+-----+-------+------+

PRD References:
    - Section E.5: Output files with cross-references
    - Section I: PRD contents and artifact linking

Author: PM-OS Team
Version: 1.1.0
"""

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class FinalizationResult:
    """Result of a finalization operation."""

    success: bool
    files_updated: List[str] = field(default_factory=list)
    links_added: List[str] = field(default_factory=list)
    message: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "files_updated": self.files_updated,
            "links_added": self.links_added,
            "message": self.message,
            "errors": self.errors,
        }


class OutputFinalizer:
    """
    Finalizes feature context files with all artifact links after output generation.

    Responsibilities:
        1. Add PRD reference to context file
        2. Add Jira epic link to context file
        3. Update BC document with approval links
        4. Update ADRs with implementation status
        5. Ensure bidirectional cross-references
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the output finalizer.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        import config_loader

        self._config = config_loader.get_config()
        self._user_path = user_path or Path(self._config.user_path)

    def finalize_context_file(
        self,
        feature_path: Path,
        prd_path: Optional[Path] = None,
        jira_epic_url: Optional[str] = None,
        spec_export_path: Optional[Path] = None,
        additional_artifacts: Optional[Dict[str, str]] = None,
    ) -> FinalizationResult:
        """
        Finalize all context files with artifact links after output generation.

        This is the main entry point called after /generate-outputs completes.

        Args:
            feature_path: Path to the feature folder
            prd_path: Path to generated PRD (if any)
            jira_epic_url: URL to Jira epic (if created)
            spec_export_path: Path to spec machine export (if any)
            additional_artifacts: Additional artifacts to link

        Returns:
            FinalizationResult with operation details
        """
        result = FinalizationResult(success=False)

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        # 1. Update context file with all artifact links
        context_result = self._update_context_file_links(
            feature_path=feature_path,
            state=state,
            prd_path=prd_path,
            jira_epic_url=jira_epic_url,
            spec_export_path=spec_export_path,
            additional_artifacts=additional_artifacts,
        )
        if context_result:
            result.files_updated.append(str(state.context_file))
            result.links_added.extend(context_result)

        # 2. Update business case document with approval links
        bc_result = self._update_business_case_links(
            feature_path=feature_path,
            state=state,
            prd_path=prd_path,
        )
        if bc_result:
            result.files_updated.extend(bc_result.get("files", []))
            result.links_added.extend(bc_result.get("links", []))

        # 3. Update ADR files with implementation status
        adr_result = self._update_adr_implementation_status(
            feature_path=feature_path,
            state=state,
            prd_path=prd_path,
        )
        if adr_result:
            result.files_updated.extend(adr_result.get("files", []))
            result.links_added.extend(adr_result.get("links", []))

        # 4. Update PRD with back-references (bidirectional)
        if prd_path and prd_path.exists():
            prd_result = self._add_prd_back_references(
                prd_path=prd_path,
                feature_path=feature_path,
                state=state,
            )
            if prd_result:
                result.files_updated.append(str(prd_path))
                result.links_added.extend(prd_result)

        # 5. Update feature state with final artifact paths
        state_updated = self._update_feature_state_artifacts(
            feature_path=feature_path,
            state=state,
            prd_path=prd_path,
            jira_epic_url=jira_epic_url,
            spec_export_path=spec_export_path,
        )
        if state_updated:
            result.files_updated.append("feature-state.yaml")

        result.success = len(result.errors) == 0
        result.message = (
            f"Finalized {len(result.files_updated)} files with {len(result.links_added)} links"
            if result.success
            else f"Finalization completed with {len(result.errors)} errors"
        )

        return result

    def update_artifact_links(
        self,
        feature_path: Path,
        artifact_type: str,
        artifact_path: str,
    ) -> FinalizationResult:
        """
        Update context files with a single artifact link.

        Called when a new artifact is attached or generated.

        Args:
            feature_path: Path to the feature folder
            artifact_type: Type of artifact (prd, jira_epic, spec_export, etc.)
            artifact_path: Path or URL to the artifact

        Returns:
            FinalizationResult with operation details
        """
        result = FinalizationResult(success=False)

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        # Map artifact types to appropriate update methods
        artifact_handlers = {
            "prd": lambda: self._add_prd_reference(
                feature_path, state, Path(artifact_path)
            ),
            "jira_epic": lambda: self._add_jira_epic_reference(
                feature_path, state, artifact_path
            ),
            "spec_export": lambda: self._add_spec_export_reference(
                feature_path, state, Path(artifact_path)
            ),
            "figma": lambda: self._add_artifact_to_references(
                feature_path, state, "Figma Design", artifact_path
            ),
            "wireframes": lambda: self._add_artifact_to_references(
                feature_path, state, "Wireframes", artifact_path
            ),
            "confluence": lambda: self._add_artifact_to_references(
                feature_path, state, "Confluence", artifact_path
            ),
        }

        handler = artifact_handlers.get(artifact_type)
        if not handler:
            result.errors.append(f"Unknown artifact type: {artifact_type}")
            return result

        try:
            updated_files = handler()
            if updated_files:
                result.files_updated = updated_files
                result.links_added.append(f"{artifact_type}: {artifact_path}")
                result.success = True
                result.message = f"Added {artifact_type} link to context files"
        except Exception as e:
            result.errors.append(f"Failed to add {artifact_type} link: {str(e)}")

        return result

    def add_prd_reference(
        self,
        feature_path: Path,
        prd_path: Path,
    ) -> FinalizationResult:
        """
        Add PRD reference to the feature context file.

        Args:
            feature_path: Path to the feature folder
            prd_path: Path to the generated PRD

        Returns:
            FinalizationResult with operation details
        """
        result = FinalizationResult(success=False)

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        try:
            updated_files = self._add_prd_reference(feature_path, state, prd_path)
            if updated_files:
                result.files_updated = updated_files
                result.links_added.append(f"PRD: {prd_path}")
                result.success = True
                result.message = "Added PRD reference to context file"
        except Exception as e:
            result.errors.append(f"Failed to add PRD reference: {str(e)}")

        return result

    def _update_context_file_links(
        self,
        feature_path: Path,
        state: Any,
        prd_path: Optional[Path] = None,
        jira_epic_url: Optional[str] = None,
        spec_export_path: Optional[Path] = None,
        additional_artifacts: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        Update the context file's References section with all artifact links.

        Ensures bidirectional linking by adding:
        - External artifacts (Figma, Jira, Confluence, Wireframes)
        - Generated documents (PRD, Spec export)
        - Internal documents (BC, ADRs)
        - Feature state reference

        Returns list of link descriptions added.
        """
        context_file = feature_path / state.context_file
        if not context_file.exists():
            return []

        content = context_file.read_text()
        links_added = []

        # Build new references based on artifacts - organized by category
        external_refs = []
        generated_refs = []
        internal_refs = []

        # === External Artifacts ===
        if state.artifacts.get("figma"):
            external_refs.append(
                f"- **Figma Design**: [{state.title} Designs]({state.artifacts['figma']})"
            )

        if state.artifacts.get("wireframes_url"):
            external_refs.append(
                f"- **Wireframes**: [Wireframes]({state.artifacts['wireframes_url']})"
            )

        if jira_epic_url or state.artifacts.get("jira_epic"):
            epic_url = jira_epic_url or state.artifacts.get("jira_epic")
            # Extract ticket ID from URL
            ticket_id = self._extract_jira_ticket_id(epic_url)
            external_refs.append(f"- **Jira Epic**: [{ticket_id}]({epic_url})")
            links_added.append("Jira Epic")

        if state.artifacts.get("confluence_page"):
            external_refs.append(
                f"- **Confluence**: [Documentation]({state.artifacts['confluence_page']})"
            )

        # === Generated Documents (bidirectional links) ===
        if prd_path:
            relative_prd = self._get_relative_path(prd_path, feature_path)
            generated_refs.append(f"- **PRD**: [{state.title}]({relative_prd})")
            links_added.append("PRD")

        if spec_export_path:
            relative_spec = self._get_relative_path(spec_export_path, feature_path)
            generated_refs.append(f"- **Spec Machine Export**: [Spec]({relative_spec})")
            links_added.append("Spec Export")

        # === Internal Documents (bidirectional links) ===
        # Business Case documents
        bc_dir = feature_path / "business-case"
        if bc_dir.exists():
            bc_files = sorted(bc_dir.glob("bc-v*-approved.md"), reverse=True)
            if not bc_files:
                bc_files = sorted(bc_dir.glob("bc-v*.md"), reverse=True)
            if bc_files:
                bc_file = bc_files[0]
                internal_refs.append(
                    f"- **Business Case**: [`{bc_file.name}`](business-case/{bc_file.name})"
                )
                links_added.append("Business Case")

        # Engineering ADRs
        adr_dir = feature_path / "engineering" / "adrs"
        if adr_dir.exists():
            adr_files = sorted(adr_dir.glob("adr-*.md"))
            if adr_files:
                for adr_file in adr_files[:3]:  # List first 3 ADRs
                    internal_refs.append(
                        f"- **{adr_file.stem.upper()}**: [`{adr_file.name}`](engineering/adrs/{adr_file.name})"
                    )
                if len(adr_files) > 3:
                    internal_refs.append(
                        f"- *({len(adr_files) - 3} more ADRs in `engineering/adrs/`)*"
                    )
                links_added.append("ADRs")

        # Feature state reference
        internal_refs.append(
            f"- **Feature State**: [`feature-state.yaml`](feature-state.yaml)"
        )

        # === Additional artifacts ===
        if additional_artifacts:
            for name, url in additional_artifacts.items():
                external_refs.append(f"- **{name}**: [Link]({url})")
                links_added.append(name)

        # Build the complete references section
        new_refs = []
        if external_refs:
            new_refs.append("**External Links:**")
            new_refs.extend(external_refs)
            new_refs.append("")

        if generated_refs:
            new_refs.append("**Generated Documents:**")
            new_refs.extend(generated_refs)
            new_refs.append("")

        if internal_refs:
            new_refs.append("**Internal Documents:**")
            new_refs.extend(internal_refs)

        # Update the References section
        if new_refs:
            refs_text = "\n".join(new_refs)
            # Find and replace References section
            pattern = r"(## References\n)(.*?)(\n## |\Z)"
            replacement = f"\\1\n{refs_text}\n\n\\3"
            new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

            if new_content != content:
                context_file.write_text(new_content)

        return links_added

    def _update_business_case_links(
        self,
        feature_path: Path,
        state: Any,
        prd_path: Optional[Path] = None,
    ) -> Optional[Dict[str, List[str]]]:
        """
        Update business case document with approval record links and bidirectional references.

        Ensures bidirectional linking:
        - BC -> PRD (Generated PRD link)
        - BC -> Context file (link)
        - BC -> Approval records (inline documentation)

        Returns dict with 'files' and 'links' lists.
        """
        bc_dir = feature_path / "business-case"
        if not bc_dir.exists():
            return None

        files_updated = []
        links_added = []

        # Find the latest approved BC or latest version
        bc_files = sorted(bc_dir.glob("bc-v*-approved.md"), reverse=True)
        if not bc_files:
            bc_files = sorted(bc_dir.glob("bc-v*.md"), reverse=True)

        if not bc_files:
            return None

        bc_file = bc_files[0]
        content = bc_file.read_text()
        modified = False

        # Build or update Related Documents section with bidirectional links
        if "## Related Documents" not in content:
            related_docs_lines = ["\n\n## Related Documents\n"]

            # Add PRD link
            if prd_path and prd_path.exists():
                relative_prd = self._get_relative_path(prd_path, feature_path)
                related_docs_lines.append(
                    f"- **Generated PRD**: [{state.title}]({relative_prd})"
                )
                links_added.append("PRD link in BC")

            # Add context file link (bidirectional)
            context_path = f"../{state.context_file}"
            related_docs_lines.append(
                f"- **Context Document**: [{state.title} Context]({context_path})"
            )
            links_added.append("Context link in BC")

            # Add feature state reference
            related_docs_lines.append(f"- **Feature State**: `../feature-state.yaml`")

            # Add engineering ADRs reference if they exist
            adr_dir = feature_path / "engineering" / "adrs"
            if adr_dir.exists() and list(adr_dir.glob("adr-*.md")):
                related_docs_lines.append(
                    f"- **Architecture Decisions**: `../engineering/adrs/`"
                )

            content += "\n".join(related_docs_lines) + "\n"
            modified = True

        elif prd_path and prd_path.exists() and "Generated PRD" not in content:
            # Related Documents exists but PRD link is missing - add it
            relative_prd = self._get_relative_path(prd_path, feature_path)
            pattern = r"(## Related Documents\n)"
            replacement = f"\\1\n- **Generated PRD**: [{state.title}]({relative_prd})\n"
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                modified = True
                links_added.append("PRD link in BC")

        # Add approval record references if approvals exist
        from .tracks.business_case import BusinessCaseTrack

        try:
            bc_track = BusinessCaseTrack(feature_path)
            if bc_track.approvals:
                # Check if approval records section exists
                if "## Approval Records" not in content:
                    approval_lines = ["\n\n## Approval Records\n"]
                    approval_lines.append(
                        "\n| Approver | Decision | Date | Type | Reference |"
                    )
                    approval_lines.append(
                        "|----------|----------|------|------|-----------|"
                    )

                    for approval in bc_track.approvals:
                        date_str = (
                            approval.date.strftime("%Y-%m-%d")
                            if approval.date
                            else "N/A"
                        )
                        status = "Approved" if approval.approved else "Rejected"
                        ref = (
                            approval.reference[:30] + "..."
                            if approval.reference and len(approval.reference) > 30
                            else (approval.reference or "N/A")
                        )
                        approval_lines.append(
                            f"| {approval.approver} | {status} | {date_str} | {approval.approval_type} | {ref} |"
                        )

                    # Add notes section if any approvals have notes
                    notes_present = [a for a in bc_track.approvals if a.notes]
                    if notes_present:
                        approval_lines.append("\n**Approval Notes:**\n")
                        for approval in notes_present:
                            approval_lines.append(
                                f"- **{approval.approver}**: {approval.notes[:200]}{'...' if len(approval.notes) > 200 else ''}"
                            )

                    content += "\n".join(approval_lines) + "\n"
                    modified = True
                    links_added.append("Approval records table")
        except Exception:
            pass  # BC track not available, skip

        # Add completion status if feature is complete
        if state.current_phase and state.current_phase.value == "complete":
            if "## Completion Status" not in content:
                today = datetime.now().strftime("%Y-%m-%d")
                content += f"\n\n## Completion Status\n\n- **Feature Status**: Complete\n- **Completion Date**: {today}\n- **PRD Generated**: Yes\n"
                modified = True
                links_added.append("Completion status in BC")

        if modified:
            bc_file.write_text(content)
            files_updated.append(str(bc_file.relative_to(feature_path)))

        return {"files": files_updated, "links": links_added} if files_updated else None

    def _update_adr_implementation_status(
        self,
        feature_path: Path,
        state: Any,
        prd_path: Optional[Path] = None,
    ) -> Optional[Dict[str, List[str]]]:
        """
        Update ADR files with implementation status and PRD links.

        Ensures bidirectional linking:
        - ADR -> PRD (Related Documents section)
        - ADR -> Context file (link)
        - Updates status from proposed to accepted when feature is complete

        Returns dict with 'files' and 'links' lists.
        """
        adr_dir = feature_path / "engineering" / "adrs"
        if not adr_dir.exists():
            return None

        files_updated = []
        links_added = []

        for adr_file in adr_dir.glob("adr-*.md"):
            content = adr_file.read_text()
            modified = False

            # Update status to reflect that feature is complete
            if state.current_phase and state.current_phase.value == "complete":
                # Update ADR status section if it shows "proposed"
                if "Status: proposed" in content:
                    content = content.replace("Status: proposed", "Status: accepted")
                    modified = True
                    links_added.append(f"{adr_file.stem} status updated")

            # Add Related Documents section with bidirectional links
            if "## Related Documents" not in content:
                related_docs_lines = ["\n\n## Related Documents\n"]

                # Add PRD link
                if prd_path and prd_path.exists():
                    relative_prd = self._get_relative_path(prd_path, feature_path)
                    related_docs_lines.append(
                        f"- **Feature PRD**: [{state.title}]({relative_prd})"
                    )
                    links_added.append(f"PRD link in {adr_file.stem}")

                # Add context file link
                context_path = f"../../{state.context_file}"
                related_docs_lines.append(
                    f"- **Context Document**: [{state.title} Context]({context_path})"
                )
                links_added.append(f"Context link in {adr_file.stem}")

                # Add feature folder reference
                related_docs_lines.append(
                    f"- **Feature Folder**: `user/products/{state.organization}/{state.product_id}/{state.slug}/`"
                )

                content += "\n".join(related_docs_lines) + "\n"
                modified = True

            elif prd_path and prd_path.exists() and "Feature PRD" not in content:
                # Related Documents exists but PRD link is missing - add it
                relative_prd = self._get_relative_path(prd_path, feature_path)
                pattern = r"(## Related Documents\n)"
                replacement = (
                    f"\\1\n- **Feature PRD**: [{state.title}]({relative_prd})\n"
                )
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    content = new_content
                    modified = True
                    links_added.append(f"PRD link added to {adr_file.stem}")

            # Add implementation date if feature is complete
            if state.current_phase and state.current_phase.value == "complete":
                if "Implementation Date:" not in content:
                    today = datetime.now().strftime("%Y-%m-%d")
                    # Insert after Status line
                    pattern = r"(Status: \w+)"
                    replacement = f"\\1\nImplementation Date: {today}"
                    new_content = re.sub(pattern, replacement, content, count=1)
                    if new_content != content:
                        content = new_content
                        modified = True
                        links_added.append(f"{adr_file.stem} implementation date")

            # Add feature completion marker
            if state.current_phase and state.current_phase.value == "complete":
                if "Feature Status:" not in content:
                    today = datetime.now().strftime("%Y-%m-%d")
                    pattern = r"(Implementation Date: \d{4}-\d{2}-\d{2})"
                    replacement = f"\\1\nFeature Status: Complete ({today})"
                    new_content = re.sub(pattern, replacement, content, count=1)
                    if new_content != content:
                        content = new_content
                        modified = True
                        links_added.append(f"{adr_file.stem} feature status")

            if modified:
                adr_file.write_text(content)
                files_updated.append(str(adr_file.relative_to(feature_path)))

        return {"files": files_updated, "links": links_added} if files_updated else None

    def _add_prd_back_references(
        self,
        prd_path: Path,
        feature_path: Path,
        state: Any,
    ) -> List[str]:
        """
        Add back-references from PRD to source documents (bidirectional linking).

        Ensures PRD links back to:
        - Context file
        - Business case documents
        - ADRs
        - Feature state

        Returns list of link descriptions added.
        """
        if not prd_path.exists():
            return []

        content = prd_path.read_text()
        links_added = []

        # Get relative path from PRD to feature folder
        try:
            relative_feature = self._get_relative_path(feature_path, prd_path.parent)
        except Exception:
            relative_feature = (
                f"user/products/{state.organization}/{state.product_id}/{state.slug}"
            )

        # Check if Source Documents section exists and needs updating
        if "## Source Documents" not in content:
            # Build dynamic source documents section based on what actually exists
            source_lines = ["\n\n## Source Documents\n"]
            source_lines.append(
                "\nAll source documents are available in the feature folder:\n"
            )
            source_lines.append(f"\n- **Feature Folder**: `{relative_feature}/`")
            source_lines.append(
                f"- **Context Document**: [`{state.context_file}`]({relative_feature}/{state.context_file})"
            )
            source_lines.append(
                f"- **Feature State**: [`feature-state.yaml`]({relative_feature}/feature-state.yaml)"
            )

            # Check for context-docs versions
            context_docs_dir = feature_path / "context-docs"
            if context_docs_dir.exists() and list(context_docs_dir.glob("v*.md")):
                source_lines.append(
                    f"- **Context Doc Versions**: `{relative_feature}/context-docs/`"
                )

            # Check for business case
            bc_dir = feature_path / "business-case"
            if bc_dir.exists():
                bc_files = sorted(bc_dir.glob("bc-v*.md"), reverse=True)
                if bc_files:
                    bc_file = bc_files[0]
                    source_lines.append(
                        f"- **Business Case**: [`{bc_file.name}`]({relative_feature}/business-case/{bc_file.name})"
                    )
                else:
                    source_lines.append(
                        f"- **Business Case**: `{relative_feature}/business-case/`"
                    )

            # Check for ADRs
            adr_dir = feature_path / "engineering" / "adrs"
            if adr_dir.exists():
                adr_files = sorted(adr_dir.glob("adr-*.md"))
                if adr_files:
                    source_lines.append(
                        f"- **Engineering ADRs** ({len(adr_files)} records):"
                    )
                    for adr_file in adr_files[:5]:  # List up to 5 ADRs
                        source_lines.append(
                            f"  - [`{adr_file.name}`]({relative_feature}/engineering/adrs/{adr_file.name})"
                        )
                    if len(adr_files) > 5:
                        source_lines.append(f"  - *(plus {len(adr_files) - 5} more)*")
                else:
                    source_lines.append(
                        f"- **Engineering ADRs**: `{relative_feature}/engineering/adrs/`"
                    )

            source_section = "\n".join(source_lines) + "\n"

            # Insert before the final line/separator if exists
            if "---\n*Generated by" in content:
                content = content.replace(
                    "---\n*Generated by", source_section + "\n---\n*Generated by"
                )
            else:
                content += source_section

            prd_path.write_text(content)
            links_added.append("Source documents section in PRD")

        return links_added

    def ensure_bidirectional_links(
        self,
        feature_path: Path,
        prd_path: Optional[Path] = None,
    ) -> FinalizationResult:
        """
        Verify and fix all bidirectional links between feature artifacts.

        This method can be called independently to audit and fix cross-references.

        Checks and ensures:
        1. Context file -> PRD
        2. PRD -> Context file
        3. Context file -> Business Case
        4. Business Case -> Context file
        5. Context file -> ADRs
        6. ADRs -> Context file
        7. PRD -> Business Case
        8. PRD -> ADRs

        Args:
            feature_path: Path to the feature folder
            prd_path: Path to the PRD (optional, will search if not provided)

        Returns:
            FinalizationResult with details of links verified/fixed
        """
        result = FinalizationResult(success=False)

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        # Find PRD if not provided
        if prd_path is None:
            prd_path_str = state.artifacts.get("prd_path")
            if prd_path_str:
                prd_path = self._user_path / prd_path_str.replace("user/", "")
                if not prd_path.exists():
                    prd_path = None

        # Track what we've verified/fixed
        verified_links = []
        fixed_links = []

        # 1. Verify context file has links to all documents
        context_file = feature_path / state.context_file
        if context_file.exists():
            content = context_file.read_text()

            # Check for PRD link
            if prd_path and prd_path.exists():
                if "**PRD**" in content:
                    verified_links.append("Context -> PRD")
                else:
                    # Fix: add PRD link
                    self._add_artifact_to_references(
                        feature_path,
                        state,
                        "PRD",
                        str(self._get_relative_path(prd_path, feature_path)),
                        is_path=True,
                    )
                    fixed_links.append("Context -> PRD (added)")

            # Check for BC link
            bc_dir = feature_path / "business-case"
            if bc_dir.exists() and list(bc_dir.glob("bc-v*.md")):
                if "Business Case" in content:
                    verified_links.append("Context -> BC")
                else:
                    fixed_links.append("Context -> BC (needs manual update)")

        # 2. Verify PRD has back-links
        if prd_path and prd_path.exists():
            prd_content = prd_path.read_text()

            if "Source Documents" in prd_content:
                verified_links.append("PRD -> Source Documents")
            else:
                self._add_prd_back_references(prd_path, feature_path, state)
                fixed_links.append("PRD -> Source Documents (added)")

        # 3. Verify BC has links
        bc_dir = feature_path / "business-case"
        if bc_dir.exists():
            bc_files = sorted(bc_dir.glob("bc-v*.md"), reverse=True)
            if bc_files:
                bc_content = bc_files[0].read_text()
                if "Related Documents" in bc_content:
                    verified_links.append("BC -> Related Documents")
                else:
                    fixed_links.append("BC -> Related Documents (needs finalize)")

        # 4. Verify ADRs have links
        adr_dir = feature_path / "engineering" / "adrs"
        if adr_dir.exists():
            for adr_file in adr_dir.glob("adr-*.md"):
                adr_content = adr_file.read_text()
                if "Related Documents" in adr_content:
                    verified_links.append(f"{adr_file.stem} -> Related Documents")
                else:
                    fixed_links.append(
                        f"{adr_file.stem} -> Related Documents (needs finalize)"
                    )

        result.links_added = fixed_links
        result.files_updated = [
            f"Verified: {len(verified_links)} links",
            f"Fixed: {len(fixed_links)} links",
        ]
        result.success = True
        result.message = f"Bidirectional link audit complete: {len(verified_links)} verified, {len(fixed_links)} fixed/noted"

        return result

    def _update_feature_state_artifacts(
        self,
        feature_path: Path,
        state: Any,
        prd_path: Optional[Path] = None,
        jira_epic_url: Optional[str] = None,
        spec_export_path: Optional[Path] = None,
    ) -> bool:
        """
        Update feature state with final artifact paths.

        Returns True if state was updated.
        """
        updated = False

        # Store PRD path in state artifacts
        if prd_path:
            relative_prd = self._get_relative_path(prd_path, self._user_path)
            if state.artifacts.get("prd_path") != str(relative_prd):
                state.artifacts["prd_path"] = str(relative_prd)
                updated = True

        # Store Jira epic URL
        if jira_epic_url and state.artifacts.get("jira_epic") != jira_epic_url:
            state.artifacts["jira_epic"] = jira_epic_url
            updated = True

        # Store spec export path
        if spec_export_path:
            relative_spec = self._get_relative_path(spec_export_path, self._user_path)
            if state.artifacts.get("spec_export_path") != str(relative_spec):
                state.artifacts["spec_export_path"] = str(relative_spec)
                updated = True

        # Update finalization timestamp
        state.artifacts["finalized_at"] = datetime.now().isoformat()
        updated = True

        if updated:
            state.save(feature_path)

        return updated

    def _add_prd_reference(
        self,
        feature_path: Path,
        state: Any,
        prd_path: Path,
    ) -> List[str]:
        """Add PRD reference to context file."""
        return self._add_artifact_to_references(
            feature_path,
            state,
            "PRD",
            str(self._get_relative_path(prd_path, feature_path)),
            is_path=True,
        )

    def _add_jira_epic_reference(
        self,
        feature_path: Path,
        state: Any,
        jira_url: str,
    ) -> List[str]:
        """Add Jira epic reference to context file."""
        ticket_id = self._extract_jira_ticket_id(jira_url)
        return self._add_artifact_to_references(
            feature_path, state, "Jira Epic", jira_url, link_text=ticket_id
        )

    def _add_spec_export_reference(
        self,
        feature_path: Path,
        state: Any,
        spec_path: Path,
    ) -> List[str]:
        """Add spec export reference to context file."""
        return self._add_artifact_to_references(
            feature_path,
            state,
            "Spec Machine Export",
            str(self._get_relative_path(spec_path, feature_path)),
            is_path=True,
        )

    def _add_artifact_to_references(
        self,
        feature_path: Path,
        state: Any,
        artifact_name: str,
        artifact_url: str,
        link_text: Optional[str] = None,
        is_path: bool = False,
    ) -> List[str]:
        """
        Add a single artifact to the context file's References section.

        Returns list of files updated.
        """
        context_file = feature_path / state.context_file
        if not context_file.exists():
            return []

        content = context_file.read_text()

        # Format the reference line
        if is_path:
            ref_line = f"- **{artifact_name}**: `{artifact_url}`"
        else:
            display_text = link_text or artifact_name
            ref_line = f"- **{artifact_name}**: [{display_text}]({artifact_url})"

        # Check if already present
        if artifact_name in content and (
            artifact_url in content or (link_text and link_text in content)
        ):
            return []

        # Find References section and add the new reference
        pattern = r"(## References\n)((?:- [^\n]+\n?)*)"
        match = re.search(pattern, content)

        if match:
            existing_refs = match.group(2).strip()
            if existing_refs == "- *No links yet*":
                # Replace placeholder
                new_refs = ref_line
            else:
                # Add to existing refs
                new_refs = existing_refs + "\n" + ref_line

            new_content = (
                content[: match.start()]
                + f"## References\n{new_refs}\n"
                + content[match.end() :]
            )

            if new_content != content:
                context_file.write_text(new_content)
                return [str(state.context_file)]

        return []

    def _get_relative_path(self, target_path: Path, base_path: Path) -> str:
        """
        Get a relative path from base to target, handling different directory trees.

        Args:
            target_path: Path to get relative path to
            base_path: Base path to calculate from

        Returns:
            Relative path string or absolute path if not possible
        """
        try:
            return str(target_path.relative_to(base_path))
        except ValueError:
            # Not under base_path, try to find common ancestor
            try:
                # Go up to user path and get relative from there
                target_relative = target_path.relative_to(self._user_path)
                return f"user/{target_relative}"
            except ValueError:
                # Fall back to absolute path
                return str(target_path)

    def _extract_jira_ticket_id(self, url: str) -> str:
        """
        Extract Jira ticket ID from URL.

        Args:
            url: Jira URL (e.g., https://atlassian.net/browse/MK-1234)

        Returns:
            Ticket ID (e.g., MK-1234) or the URL if extraction fails
        """
        # Match pattern like /browse/PROJECT-123 or /PROJECT-123
        match = re.search(r"/([A-Z]+-\d+)", url)
        if match:
            return match.group(1)

        # Try to get just the last path segment
        if "/" in url:
            last_segment = url.rstrip("/").split("/")[-1]
            if re.match(r"^[A-Z]+-\d+$", last_segment):
                return last_segment

        return url


# Convenience functions


def finalize_feature_outputs(
    feature_path: Path,
    prd_path: Optional[Path] = None,
    jira_epic_url: Optional[str] = None,
    spec_export_path: Optional[Path] = None,
) -> FinalizationResult:
    """
    Finalize all feature context files with artifact links.

    Convenience function for the common finalization workflow.

    Args:
        feature_path: Path to the feature folder
        prd_path: Path to generated PRD
        jira_epic_url: URL to Jira epic
        spec_export_path: Path to spec machine export

    Returns:
        FinalizationResult with operation details
    """
    finalizer = OutputFinalizer()
    return finalizer.finalize_context_file(
        feature_path=feature_path,
        prd_path=prd_path,
        jira_epic_url=jira_epic_url,
        spec_export_path=spec_export_path,
    )


def add_prd_to_context(
    feature_path: Path,
    prd_path: Path,
) -> FinalizationResult:
    """
    Add PRD reference to feature context file.

    Args:
        feature_path: Path to the feature folder
        prd_path: Path to the generated PRD

    Returns:
        FinalizationResult with operation details
    """
    finalizer = OutputFinalizer()
    return finalizer.add_prd_reference(feature_path, prd_path)


def update_all_artifact_links(
    feature_path: Path,
    artifacts: Dict[str, str],
) -> FinalizationResult:
    """
    Update context files with multiple artifact links.

    Args:
        feature_path: Path to the feature folder
        artifacts: Dictionary mapping artifact type to path/URL

    Returns:
        Combined FinalizationResult
    """
    finalizer = OutputFinalizer()
    combined_result = FinalizationResult(success=True)

    for artifact_type, artifact_path in artifacts.items():
        result = finalizer.update_artifact_links(
            feature_path=feature_path,
            artifact_type=artifact_type,
            artifact_path=artifact_path,
        )
        combined_result.files_updated.extend(result.files_updated)
        combined_result.links_added.extend(result.links_added)
        combined_result.errors.extend(result.errors)

    combined_result.success = len(combined_result.errors) == 0
    combined_result.message = f"Updated {len(combined_result.files_updated)} files with {len(combined_result.links_added)} links"

    return combined_result


def verify_bidirectional_links(
    feature_path: Path,
    prd_path: Optional[Path] = None,
) -> FinalizationResult:
    """
    Verify and fix all bidirectional links between feature artifacts.

    This is a convenience function for auditing cross-references.

    Args:
        feature_path: Path to the feature folder
        prd_path: Path to the PRD (optional)

    Returns:
        FinalizationResult with audit details
    """
    finalizer = OutputFinalizer()
    return finalizer.ensure_bidirectional_links(feature_path, prd_path)
