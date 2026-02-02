# Project Rules and Governance

## 1. Governance Workflow
All changes must rigidly follow this cycle:
1.  **Plan**: Define the scope, objectives, and approach.
2.  **Review**: Submit the plan for user review. **DO NOT PROCEED** without explicit approval.
3.  **Analyze**: Perform a detailed impact analysis on system integrity and functional flow.
4.  **Implement**: Execute the changes only after the above steps are complete.

## 2. Requirement Preservation
-   **Freeze Policy**: Existing requirements are considered **FROZEN**. They must remain intact unless explicitly authorized to change.
-   **Context Retention**: Every new prompt and task must actively "remember" and verify against existing requirements.
-   **Contradictions**: If a new request contradicts an existing requirement, the conflict must be **immediately invoked and discussed** with the user before any planning or implementation occurs.

## 3. Impact Analysis
-   Every proposed change must be analyzed for:
    -   **System Integrity**: Will this break existing architecture or security?
    -   **Functional Flow**: Will this alter the user experience or current features?

## 4. Documentation & Traceability
-   **Progress Tracking**: All `.md` files in the `proj-progress/` folder must be updated or added to whenever *any* update or change occurs.
-   **Baseline**: `REQUIREMENTS_BASELINE.md` serves as the source of truth for the project state at the start of this governance era.

## 5. Implementation Integrity
-   No code changes shall be made that bypass the Plan-Review-Analyze cycle.
-   All tasks must track their status in `task.md` (or equivalent) in real-time.
