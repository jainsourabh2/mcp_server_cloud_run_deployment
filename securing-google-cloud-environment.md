# Securing Your Google Cloud Environment: A Practical Guide to Org Policies, Resource Alerts, Spend Caps, and SCC

In today's multi-tenant and fast-paced cloud environments, securing Google Cloud Platform (GCP) requires more than just reactive monitoring or basic Identity and Access Management (IAM) role assignments. Organizations need proactive guardrails, real-time alerting on critical events, automated financial safety nets, and centralized security posture management.

Whether you are a Lead DevOps Engineer, Cloud Security Architect, or Infrastructure Administrator, this guide covers **four essential pillars** to fortify your GCP ecosystem against misconfigurations, rogue resource provisioning, unexpected costs, and security threats.

---

## Executive Summary: The 4 Core Pillars

| Pillar | Key Objective | Key GCP Service | Impact |
| :--- | :--- | :--- | :--- |
| **1. Organization Policies** | Enforce governance & restrict risky operations across all projects | GCP Org Policy Service | Prevents misconfigurations before they occur |
| **2. Cloud Logging Alerting** | Real-time detection when high-impact resources (VMs, GPUs, SQL) are created | Cloud Audit Logs + Cloud Monitoring | Immediate detection of shadow IT or cryptomining |
| **3. Spend Cap Controls** | Prevent run-away cloud bills and financial exploitation | Cloud Billing + Pub/Sub + Cloud Functions | Protects against budget overruns & billing attacks |
| **4. Security Command Center** | Org-wide visibility, vulnerability management & threat detection | Security Command Center (SCC) | Centralized security dashboard & asset tracking |

---

## Pillar 1: Applying Organization Policies (Guardrails at Scale)

### What are Organization Policies?
Google Cloud Organization Policies allow administrators to set central, programmatic guardrails across the entire resource hierarchy (**Organization → Folders → Projects**). Unlike IAM (which controls *who* can perform an action), Org Policies dictate *what* can or cannot be done with cloud resources regardless of a user's IAM permissions.

```
                  ┌──────────────────────────────┐
                  │      Organization Node       │
                  │  [ Org Policies Enforced ]   │
                  └──────────────┬───────────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
            ┌──────────────┐            ┌──────────────┐
            │   Folder A   │            │   Folder B   │
            └──────┬───────┘            └──────┬───────┘
                   │                           │
                   ▼                           ▼
            ┌──────────────┐            ┌──────────────┐
            │  Project 101 │            │  Project 102 │
            └──────────────┘            └──────────────┘
```

### Essential Org Policy Constraints to Enforce

1. **Disable Service Account Key Creation (`constraints/iam.disableServiceAccountKeyCreation`)**
   - **Risk Addressed**: Exported JSON service account keys are the #1 source of leaked GCP credentials in public repositories.
   - **Policy Action**: Force teams to use Workload Identity Federation or short-lived tokens instead of downloading service account JSON keys.

2. **Restrict Public External IP Creation (`constraints/compute.vmExternalIpAccess`)**
   - **Risk Addressed**: Unintentional exposure of Compute Engine instances to the open internet.
   - **Policy Action**: Block public IP assignment on VMs unless explicitly whitelisted for edge instances (e.g., bastion hosts or NAT gateways).

3. **Domain-Restricted Sharing (`constraints/iam.allowedPolicyMemberDomains`)**
   - **Risk Addressed**: Accidental granting of IAM access to external personal Gmail accounts or unauthorized third-party domains.
   - **Policy Action**: Restrict IAM binding additions strictly to your organization's Google Workspace / Cloud Identity Customer ID.

5. **Restrict Allowed Gemini & Model Garden AI Models (`constraints/vertexai.allowedModels`)**
   - **Risk Addressed**: Developers or service accounts invoking unapproved AI models, deprecated foundation models, or running unauthorized fine-tuning (`:tune`) jobs in Vertex AI Model Garden.
   - **Policy Action**: Maintain a central allowlist specifying permitted model versions and allowed actions (e.g., `publishers/google/models/gemini-2.0-flash:predict`, `publishers/google/models/gemini-1.5-pro-002:predict`).

6. **Restrict Partner Model Advanced Features (`constraints/vertexai.allowedPartnerModelFeatures`)**
   - **Risk Addressed**: Third-party partner models (such as Anthropic Claude) executing unmonitored external web searches or unapproved tool features within your enterprise perimeter.
   - **Policy Action**: Explicitly control which partner models and features (e.g. `:web_search` or `:structured_outputs`) are enabled across your organization.

### How to Enforce Org Policies

#### Via `gcloud` CLI

*1. Restrict Service Account Key Creation (`SA_KEY_POLICY.yaml`):*
```yaml
constraint: constraints/iam.disableServiceAccountKeyCreation
listPolicy:
  allValues: DENY
```
```bash
gcloud org-policies set-policy SA_KEY_POLICY.yaml --organization=YOUR_ORGANIZATION_ID
```

*2. Enforce Approved Gemini & Partner Models (`VERTEX_MODELS_POLICY.yaml`):*
```yaml
name: organizations/YOUR_ORGANIZATION_ID/policies/vertexai.allowedModels
spec:
  rules:
    - values:
        allowedValues:
          - publishers/google/models/gemini-2.0-flash:predict
          - publishers/google/models/gemini-1.5-pro-002:predict
          - publishers/google/models/gemini-1.5-flash-002:predict
          - publishers/anthropic/models/claude-sonnet-4:predict
```
```bash
gcloud org-policies set-policy VERTEX_MODELS_POLICY.yaml --organization=YOUR_ORGANIZATION_ID
```

*3. Restrict Partner Model Advanced Features (`PARTNER_FEATURES_POLICY.yaml`):*
```yaml
name: organizations/YOUR_ORGANIZATION_ID/policies/vertexai.allowedPartnerModelFeatures
spec:
  rules:
    - values:
        allowedValues:
          - publishers/anthropic/models/claude-sonnet-4:structured_outputs
          # Explicitly exclude web_search if unapproved
```

#### Via Terraform (Recommended for Infrastructure-as-Code)
```hcl
# Disable Service Account JSON Key Creation
resource "google_organization_policy" "disable_sa_key_creation" {
  org_id     = var.organization_id
  constraint = "constraints/iam.disableServiceAccountKeyCreation"

  boolean_policy {
    enforced = true
  }
}

# Restrict Allowed Gemini & Partner Models in Vertex AI
resource "google_org_policy_policy" "allowed_vertex_models" {
  name   = "organizations/${var.organization_id}/policies/vertexai.allowedModels"
  parent = "organizations/${var.organization_id}"

  spec {
    rules {
      values {
        allowed_values = [
          "publishers/google/models/gemini-2.0-flash:predict",
          "publishers/google/models/gemini-1.5-pro-002:predict",
          "publishers/google/models/gemini-1.5-flash-002:predict",
          "publishers/anthropic/models/claude-sonnet-4:predict"
        ]
      }
    }
  }
}
```

---

## Pillar 2: Real-Time Alerting on VM, GPU, and SQL Instance Creation

### Why Real-Time Resource Creation Alerting Matters
Unauthorized or compromised credentials are often exploited to spin up expensive Compute Engine instances, high-powered GPU workloads (for cryptomining), or exposed Cloud SQL databases. By tapping into **Cloud Audit Logs**, security teams can trigger near-instant notifications whenever high-value or high-risk resources are provisioned.

```
┌───────────────────┐    Audit Logs    ┌──────────────────┐    Log Metric    ┌────────────────────┐
│ Resource Creation │ ───────────────> │  Cloud Logging   │ ───────────────> │  Cloud Monitoring  │
│ (VM / GPU / SQL)  │                  └──────────────────┘                  └─────────┬──────────┘
└───────────────────┘                                                                  │
                                                                                       ▼
                                                                             ┌────────────────────┐
                                                                             │ Alert Notification │
                                                                             │(Slack/Email/Pager) │
                                                                             └────────────────────┘
```

### Step 1: Write the Audit Log Filter Query
In **Cloud Logging**, Admin Activity audit logs capture all resource creation events. The following filter isolates VM creation, GPU instance attached creation, and Cloud SQL instance creation:

```kql
protoPayload.serviceName=("compute.googleapis.com" OR "sqladmin.googleapis.com")
AND protoPayload.methodName=(
  "v1.compute.instances.insert" OR
  "beta.compute.instances.insert" OR
  "cloudsql.instances.create"
)
AND protoPayload.response.status="RUNNING" OR protoPayload.operation.first="true"
```

*To specifically isolate GPU allocations:*
```kql
protoPayload.serviceName="compute.googleapis.com"
AND protoPayload.methodName="v1.compute.instances.insert"
AND protoPayload.request.guestAccelerators:*
```

### Step 2: Create a Log-Based Metric
1. Navigate to **Logging > Log-based Metrics** in the GCP Console.
2. Click **Create Metric**.
3. Choose **Counter** type.
4. Set Name: `high_impact_resource_creation_count`.
5. Paste the KQL audit log filter above.

### Step 3: Configure Cloud Monitoring Alerting Policy
1. Go to **Monitoring > Alerting** and click **Create Policy**.
2. Select the log-based metric `workload.googleapis.com/high_impact_resource_creation_count`.
3. Set the threshold trigger: `Above 0 for 1 minute`.
4. Configure **Notification Channels**:
   - **Slack Webhook** / **PagerDuty** for Security Operations Center (SOC) teams.
   - **Email / SMS** for On-Call Cloud Administrators.
5. Provide actionable documentation in the Alerting Message:
   > **ALERT**: A new high-capacity Compute Engine VM, GPU, or Cloud SQL instance was created in project `${resource.label.project_id}` by user `${metric.label.principal_email}`. Verify authorization immediately.

---

## Pillar 3: Spend Cap Configuration & Cost Control

### The Security & Cost Connection
Cloud security and cost control are deeply intertwined. A compromised credential or runaway autoscaling script can incur thousands of dollars in minutes. While standard budgets send notification alerts, Google Cloud Billing offers native **Spend Cap Budgets** that automatically pause service usage when costs exceed 100% of your target amount.

---

### How Native Spend Cap Budgets Work
Spend Cap budgets monitor estimated gross usage costs in real time. When usage reaches **100% of your target budget amount**, Google Cloud automatically blocks new API calls and pauses usage for the specified service in the project.

```
┌────────────────────────┐      Gross Estimated Costs >= 100%      ┌─────────────────────────┐
│ Cloud Billing Budget   │ ──────────────────────────────────────> │ Automatic Usage Pause   │
│ (Spend Cap Enforced)   │                                         │ (New Requests Blocked)  │
└───────────┬────────────┘                                         └────────────┬────────────┘
            │                                                                   │
            │ Alerts Sent @ 50%, 80%, 100%                                      │ Requires Manual Lift
            ▼                                                                   ▼
┌────────────────────────┐                                         ┌─────────────────────────┐
│ Email & Console Banners│                                         │ Admin Lifts Spend Cap   │
│ (Billing Admins/Owners)│                                         │ (Resumes Service Usage) │
└────────────────────────┘                                         └─────────────────────────┘
```

#### Key Characteristics & Behavior:
- **Automatic Pause**: When enforced, new requests to the capped service in the project are blocked.
- **In-flight Requests**: Active in-flight requests process to completion.
- **Persistent Resources**: On-going fixed usage for persistent resources (such as Compute Engine VMs or Cloud Storage) remains active and continues to accrue charges.
- **Manual Intervention Required**: Paused usage is **only restored when an administrator manually lifts the spend cap** in the Cloud Billing console.
- **Automatic Monthly Reset**: Once lifted (or at the start of a new month), the spend cap resets automatically for the next monthly budget period.

#### Supported Eligible Services:
Native Cloud Billing Spend Caps currently support key API-based and serverless services:
- **Gemini API**
- **Gemini Enterprise Agent Platform** (formerly Vertex AI)
- **Cloud Run**
- **Cloud Run functions**

*(Note: For services outside native spend cap coverage such as Compute Engine or BigQuery, organizations can optionally connect budget alerts to Pub/Sub and Cloud Functions to programmatically adjust quotas or detach billing).*

---

### Required IAM Permissions
To configure and manage Spend Cap budgets, you need one of the following IAM role combinations:
- **Billing Account Administrator** on the Cloud Billing account (OR **Project Owner** on the target project).
- **Billing Account Costs Manager** AND **Project Editor** on the target project.

---

### Step-by-Step: How to Configure a Native Spend Cap Budget

#### Step 1: Define the Budget
1. In the Google Cloud console, navigate to **Billing > Budgets & alerts**.
2. Click **Create new budget**. *(Note: Existing alerts-only budgets cannot be converted; you must create a new budget).*
3. Under the **Define** section, select **Spend cap enforcement** (instead of *Alerts only*).
4. Enter a descriptive **Name** for your budget (e.g., `spend-cap-cloud-run-dev-project`).
5. Click **Next**.

#### Step 2: Set the Scope
1. **Time range**: Automatically set to **Monthly** (starts on the 1st of each month; cannot be changed for spend cap budgets).
2. **Projects**: Select a **single Project** from the dropdown.
3. **Services**: Select a **single eligible Service** (e.g., *Gemini API*, *Vertex AI*, *Cloud Run*, or *Cloud Run functions*).
4. Click **Next**.

#### Step 3: Specify Target Amount
1. **Budget type**: Automatically locked to **Specified amount**.
2. Enter the **Target amount** (e.g., `$500.00`).
   > **Pro Tip**: Because spend caps enforce based on gross estimated usage and cost processing latency can take a short time, consider setting your spend cap slightly below your absolute max limit.
3. Click **Next**.

#### Step 4: Review Actions & Enable
1. **Spend cap notifications** are automatically configured to notify all Billing Account Administrators and Project Owners at **50%**, **80%**, and **100%** of the target budget.
2. Click **Finish** to save and activate your spend cap budget.

---

### How to View & Lift an Enforced Spend Cap

#### Checking Spend Cap Status
In the **Budgets & alerts** dashboard, monitor the **Spend cap status** column:
- **Configured**: Spend cap budget is active and monitoring costs.
- **Enforced**: Spending hit 100%; usage for the selected service is currently paused.
- **Lifted**: An administrator manually unpaused the spend cap for the rest of the billing month.

#### Lifting an Enforced Cap
When a cap triggers, administrators receive an email alert and console banners on the Billing Overview page.

To unblock API calls and resume service usage:
1. Go to **Billing > Budgets & alerts**.
2. Click **View spend cap details** on the informational banner (or filter by *Enforced*).
3. Select the budget name to open the **Edit budget** screen.
4. Click **Lift spend cap**.
5. Click **Confirm**.

> 💡 **Note**: After lifting a spend cap, services take up to **one hour** to fully resume normal function. Once lifted within a month, the cap will not trigger again until the next billing month unless you increase the target threshold amount.

---

## Pillar 4: Enabling Security Command Center (SCC) at the Organization Level

### Why Enable Security Command Center (SCC) at the Org Level?
**Security Command Center (SCC)** is Google Cloud's centralized security and risk management platform. While project-level enabling offers localized visibility, enabling SCC at the **Organization Level** is essential for enterprise security governance because it provides:

1. **Global Asset Inventory**: Automatic discovery and asset tracking of all Compute instances, IAM policies, GCS buckets, and networks across all current and future projects.
2. **Centralized Misconfiguration Detection**: Built-in Security Health Analytics (SHA) continuously scans for common risks (e.g., world-readable Cloud Storage buckets, open SSH ports, disabled log export).
3. **Unified Threat Detection**: Detects real-time threats like anomalous service account activity, credential exposure, malware, and rogue container executions across the organization.

```
                             ┌───────────────────────────────────┐
                             │    GCP Organization Root Node     │
                             │  ┌─────────────────────────────┐  │
                             │  │ Security Command Center (SCC)│  │
                             │  └──────────────┬──────────────┘  │
                             └─────────────────┼─────────────────┘
                                               │
             ┌─────────────────────────────────┼─────────────────────────────────┐
             ▼                                 ▼                                 ▼
   ┌───────────────────┐             ┌───────────────────┐             ┌───────────────────┐
   │ Asset Discovery   │             │ Security Health   │             │ Event Threat      │
   │ & Inventory       │             │ Analytics (SHA)   │             │ Detection (ETD)   │
   └───────────────────┘             └───────────────────┘             └───────────────────┘
```

### SCC Service Tiers: Standard vs Enterprise
- **SCC Standard**: Included at no extra charge. Provides basic asset discovery and fundamental misconfiguration scanning (e.g., open storage buckets, exposed administrative ports).
- **SCC Enterprise / Premium**: Adds Advanced Event Threat Detection (ETD), Container Threat Detection, Rapid Vulnerability Detection, Compliance Benchmarks (CIS, PCI-DSS, NIST), and automated remediation integration.

### Steps to Enable SCC at the Organization Level

#### Step 1: Verify Prerequisites & Roles
Ensure you have the following IAM roles at the Organization level:
- `roles/securitycenter.admin` (Security Command Center Admin)
- `roles/resourcemanager.organizationAdmin` (Organization Admin)

#### Step 2: Onboard SCC via GCP Console
1. Log into the Google Cloud Console and select your **Organization node** from the project picker.
2. Navigate to **Security > Security Command Center**.
3. Click **Select Tier** (Choose Standard or Enterprise/Premium).
4. Select the built-in services to enable:
   - Security Health Analytics
   - Web Security Scanner
   - Event Threat Detection
5. Grant the default SCC Service Account permission to scan resources across the organization.

#### Step 3: Export SCC Findings to BigQuery or Security Operations (SIEM)
To maintain long-term audit records or integrate with SIEM solutions (like Chronicle, Splunk, or Datadog):
1. Go to **Security Command Center > Settings > Continuous Exports**.
2. Click **Create Pub/Sub Export** or **BigQuery Export**.
3. Stream all high-severity and critical findings in real time for automated SOC ingestion.

---

## Security Best Practices Checklist

To ensure your GCP environment is thoroughly protected, use this quick checklist:

- [ ] **Org Policies Enforced**: Service account JSON keys disabled, external VM IPs restricted, and IAM sharing limited to your domain.
- [ ] **Cloud Audit Logging Active**: Admin Activity and Data Access logs enabled for core services (`compute`, `sqladmin`, `iam`).
- [ ] **Real-time Alerting Configured**: Log-based metrics and alerts created for VM, GPU, and Cloud SQL provisioning events.
- [ ] **Budget Notifications & Caps Set**: Budgets set with thresholds at 50%, 80%, 100%, and Pub/Sub integrations active for automated capping in sandbox projects.
- [ ] **SCC Enabled at Org Level**: SCC running on the root organization node with BigQuery/Pub/Sub export enabled for critical findings.

---

## Conclusion

Securing a Google Cloud environment does not have to be an overwhelming challenge. By implementing **Organization Policies** as proactive guardrails, setting up **Cloud Logging alerts** for sensitive resource creation, establishing **Spend Caps** to avoid financial exploitation, and unifying visibility with **Security Command Center at the organization level**, you create a robust, multi-layered defense posture.

Start by auditing your current GCP organization node today and enforcing these four foundational controls!
