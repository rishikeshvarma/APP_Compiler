# Design Specification: HealthSync CRM (HIPAA-Compliant)
**Version:** 1.0.0
**Role:** Senior Systems Architect
**Status:** Draft / For Review

---

## 1. Feature Map (UI Views)

### 1.1 Patient Portal
*   **Patient Dashboard:** Overview of upcoming appointments, recent test results, and unread messages.
*   **Medical History Timeline:** A chronological view of diagnoses, prescriptions, and lab results.
*   **Secure Message Center:** 
    *   *Inbox/Thread View:* End-to-end encrypted messaging interface.
    *   *Compose:* Recipient restricted to the patient’s assigned primary or specialist doctors.
*   **Profile & Consent:** Management of HIPAA privacy authorizations and personal data.

### 1.2 Doctor Portal
*   **Patient Queue:** 
    *   *Standard:* Chronological list of patients waiting for consultation.
    *   *Premium (Gated):* Priority-sorted queue based on urgency and AI-triaged risk scores.
*   **Patient Chart View:** Deep dive into patient history, vitals, and longitudinal data.
*   **Diagnostic AI Assistant (Premium Gated):** A side-panel interface providing differential diagnosis suggestions and clinical trial matching based on patient data.
*   **Telehealth/Messaging Interface:** Real-time chat with notification triggers.

### 1.3 Admin Portal (Clinic Level)
*   **Clinic Dashboard:** High-level metrics (patient volume, response times).
*   **User Management:** Provisioning and de-provisioning of Doctor and Staff accounts.
*   **Audit Log Viewer:** Immutable log of every "Read" and "Write" action on PHI (Protected Health Information).
*   **Plan Management:** Toggle clinic-wide access to Premium features.

### 1.4 System Admin (SaaS Provider)
*   **Global Clinic Management:** Onboarding new medical practices.
*   **Compliance Dashboard:** Monitoring encryption status and system-wide security events.

---

## 2. Data Entities (ERD Blueprint)

### 2.1 Core Entities
| Entity | Properties | Relationships |
| :--- | :--- | :--- |
| **User** | ID, Email (Encrypted), PasswordHash, Role, MFA_Secret | 1:1 with Profile |
| **Clinic** | ID, Name, Plan_Type (Basic/Premium), BAA_Signed_Date | 1:N with Users, Patients |
| **PatientProfile** | ID, User_ID, DOB, SSN (Encrypted), Insurance_Info | N:M with Doctors |
| **MedicalRecord** | ID, Patient_ID, Doctor_ID, Data_Type, Encrypted_Payload | N:1 with Patient |
| **Message** | ID, Sender_ID, Receiver_ID, Ciphertext, Sent_At | 1:1 with Notification |
| **Notification** | ID, User_ID, Message_ID, Type, Is_Read, Delivered_At | N:1 with User |
| **AuditLog** | ID, Actor_ID, Action (READ/WRITE), Resource_ID, IP, Timestamp | Immutable |

### 2.2 Relationship Logic
*   **Messaging Trigger:** A DB `AFTER INSERT` trigger or Service Layer Hook ensures that for every `Message` record created, a corresponding `Notification` record is generated for the `Receiver_ID`.
*   **Encryption:** All `Encrypted_Payload` and `Ciphertext` fields must use AES-256-GCM. Keys must be rotated via a Key Management Service (KMS).

---

## 3. Auth Rules & Feature Gating

### 3.1 Role-Based Access Control (RBAC)

| Role | Permissions |
| :--- | :--- |
| **Patient** | Read own `MedicalRecord`, Create `Message` (to assigned Doctor), Read own `Notification`. |
| **Doctor** | Read/Write assigned `MedicalRecord`, Access `Patient Queue`, Create `Message`. |
| **Clinic Admin** | Read `AuditLog` for their clinic, Manage `User` roles, View Billing. Cannot view PHI `Encrypted_Payload`. |
| **System Admin** | Global system health, manage `Clinics`. No access to PHI or Audit Logs of specific clinics. |

### 3.2 Feature Gating (SaaS Tiers)

Access is controlled via a middleware check on the `Clinic.Plan_Type` attribute.

*   **Standard Plan:**
    *   Basic Patient Queue (Order by `Created_At`).
    *   Standard Secure Messaging.
*   **Premium Clinic Plan:**
    *   `FEATURE_DIAGNOSTIC_AI`: Enables the AI Assistant view and API endpoints.
    *   `FEATURE_PRIORITY_QUEUE`: Enables advanced sorting logic in the Patient Queue.
    *   `FEATURE_ANALYTICS_PRO`: Advanced reporting for Admin users.

### 3.3 HIPAA Compliance Guards
1.  **Automatic Logouts:** Session TTL set to 15 minutes of inactivity.
2.  **Audit Integrity:** The `AuditLog` table is "Insert-Only." No `UPDATE` or `DELETE` permissions are granted to any database user, including the application service account (enforced via DB-level IAM).
3.  **PHI Masking:** UI components mask sensitive data (e.g., SSN, Full Name) unless the user explicitly clicks a "View" button, which triggers a specific `ACCESS_SENSITIVE_DATA` Audit Log entry.

---

## 4. Implementation Logic: Notification Workflow

```typescript
// Architectural Pattern: Observer or Service Middleware
async function sendMessage(senderId, receiverId, content) {
    // 1. Encrypt Content
    const encryptedContent = kms.encrypt(content);

    // 2. Persist Message (Atomic Transaction)
    const message = await db.transaction(async (tx) => {
        const msg = await tx.messages.create({
            senderId,
            receiverId,
            content: encryptedContent
        });

        // 3. Mandatory Notification Creation
        await tx.notifications.create({
            userId: receiverId,
            messageId: msg.id,
            type: 'NEW_MESSAGE',
            status: 'UNREAD'
        });

        // 4. Create Audit Log entry
        await tx.auditLogs.create({
            actorId: senderId,
            action: 'SEND_MESSAGE',
            resourceId: msg.id
        });

        return msg;
    });

    return message;
}
```