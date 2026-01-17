# The Architecture and Utility of coreason-publisher

### 1. The Philosophy (The Why)
coreason-publisher acts as the "Regulatory Gatekeeper" for GxP-compliant AI systems. In the unregulated world, an AI "release" might just be a git tag. In the clinical world, an agent is a "Thick Artifact"—an inseparable bundle of Code, Model Weights, and Evidence (Test Results). The author's insight is that "Nothing merges without SRB Signature." This package solves the "Big AI" problem by enforcing a strict Two-Stage Governance Workflow (Submission $\to$ SRB Approval) and transforming mutable development experiments into immutable, verifiable clinical products. It treats Governance as Code, ensuring that every release carries a cryptographically signed audit trail that links the specific weights to the specific test results that validated them.

### 2. Under the Hood (The Dependencies & logic)
The architecture leverages a robust stack to handle the weight of ML artifacts and the strictness of compliance:
*   **`gitpython` & `Git LFS`**: These form the backbone of the "Artifact Bundler." The system automatically detects heavy files (like `.pt` or `.safetensors` weights) and hands them off to Large File Storage, or creates immutable pointers for files exceeding 70GB. This keeps the repository lean while ensuring the "Thick Artifact" is complete.
*   **`python-gitlab`**: This drives the "Workflow Engine." It abstracts the API calls required to manage Merge Requests, acting as the bridge between the local CLI and the remote governance state.
*   **`jinja2`**: Used by the `CertificateGenerator` to dynamically render the `CERTIFICATE.md` (Certificate of Analysis) from raw JSON evidence, ensuring human-readable compliance docs are generated from machine-readable data.
*   **`pydantic-settings`**: Ensures strict configuration management for environment variables and project settings.

Internally, the logic revolves around the `PublisherOrchestrator`, which manages the state transitions. The `ArtifactBundler` executes the physical preparation—moving fine-tuned adapters to `models/distilled/` and locking the "Council of Models" (the specific LLM versions used for testing) into a `council_manifest.lock`. Crucially, the `ElectronicSigner` provides the GxP seal: it calculates a deterministic SHA-256 hash of the entire release candidate (excluding `.git`) and requires an SRB member to cryptographically sign this hash before the `final_release` method will allow a merge to `main`.

### 3. In Practice (The How)
The following examples demonstrate the "Happy Path" of a release, moving from an SRE's proposal to an SRB's approval.

**The Proposal (SRE)**
The SRE triggers the release process. The system bundles the artifacts, signs the candidate, and opens a Merge Request.
```python
from coreason_publisher.main import get_orchestrator
from coreason_publisher.core.version_manager import BumpType

# Initialize the Orchestrator with all dependencies injected
orchestrator = get_orchestrator()

# SRE proposes a new feature release
# This bundles weights, generates the council snapshot, and signs the candidate
orchestrator.propose_release(
    project_id="proj_123",
    foundry_draft_id="draft_abc",
    bump_type=BumpType.MINOR,
    sre_user_id="sre_jane_doe",
    release_description="Added new fine-tuned adapter for medical coding."
)
```

**The Approval (SRB)**
Once the Scientific Review Board reviews the evidence in the MR, they sign off. The system verifies the signature against the artifact hash before merging.
```python
# SRB finalizes the release after reviewing the Evidence and CoA
# The signature is a cryptographic hash of the valid artifact
orchestrator.finalize_release(
    mr_id=42,
    srb_signature="a1b2c3d4...",  # Provided by the SRB member
    srb_user_id="srb_dr_smith"
)
```
In this workflow, `finalize_release` performs the critical check: `electronic_signer.verify_signature`. If the artifact on disk differs by even a single byte from what the SRB signed, the merge is rejected, ensuring total integrity.
