import type { Casing, FieldKind } from "@/lib/validation";

export interface FieldDef {
  name: string;
  label: string;
  type: "text" | "number" | "select" | "password" | "textarea" | "country" | "state" | "domain";
  required?: boolean;
  placeholder?: string;
  // For type "textarea": number of visible rows.
  rows?: number;
  // Helper text shown under the field (e.g. available placeholders).
  hint?: string;
  // For type "select": where to load options + which fields are value/label.
  optionsEndpoint?: string;
  optionValue?: string;
  optionLabel?: string;
  // --- validation metadata (mirrors backend core/validation.py) ---
  kind?: FieldKind; // character/format rule
  casing?: Casing; // normalisation applied on blur (upper/title/trim)
  maxLength?: number;
}

export interface ResourceConfig {
  key: string; // sidebar key
  label: string; // plural display
  singular: string; // for "Add {singular}"
  endpoint: string; // API path
  pk: string; // primary-key field
  columns: { key: string; header: string }[];
  fields: FieldDef[];
  // Field groups that must each be unique (case-/space-insensitive). Used for
  // instant duplicate + reactivate detection against the loaded rows.
  dedupeGroups?: string[][];
  // Field used for "similar record" fuzzy warnings.
  similarField?: string;
  // When set, `field` is an auto-generated, frozen system identifier derived
  // from the `source` display name — rendered read-only, never user-edited.
  autoCode?: { field: string; source: string };
}

/** Master/reference tables editable by Admin. Add a table = add an entry here. */
export const RESOURCES: ResourceConfig[] = [
  {
    key: "users",
    label: "Users",
    singular: "user",
    endpoint: "/users/",
    pk: "user_id",
    dedupeGroups: [["username"], ["email"]],
    similarField: "full_name",
    columns: [
      { key: "full_name", header: "Name" },
      { key: "username", header: "Username" },
      { key: "email", header: "Email" },
      { key: "role_name", header: "Role" },
    ],
    fields: [
      { name: "full_name", label: "Full name", type: "text", required: true, kind: "person", casing: "title", maxLength: 100 },
      { name: "username", label: "Username", type: "text", required: true, kind: "handle", maxLength: 50 },
      { name: "email", label: "Email", type: "text", required: true, kind: "email", maxLength: 150 },
      { name: "mobile", label: "Mobile", type: "text", kind: "phone", maxLength: 15 },
      {
        name: "role",
        label: "Role",
        type: "select",
        required: true,
        optionsEndpoint: "/roles/",
        optionValue: "role_id",
        optionLabel: "role_name",
      },
      { name: "password", label: "Password", type: "password", required: true, placeholder: "Set a password" },
    ],
  },
  {
    key: "skills",
    label: "Skills",
    singular: "skill",
    endpoint: "/skills/",
    pk: "skill_id",
    dedupeGroups: [["skill_name"]],
    similarField: "skill_name",
    columns: [
      { key: "skill_name", header: "Skill" },
      { key: "domain_name", header: "Domain" },
    ],
    fields: [
      { name: "skill_name", label: "Skill name", type: "text", required: true, kind: "skill", casing: "title", maxLength: 80 },
      // Domain is a FK to the Domain master (searchable dropdown + admin-only inline add).
      { name: "domain", label: "Domain", type: "domain", required: true },
    ],
  },
  {
    // Classification master for Skills. Managed Admin-only as a lightweight
    // section inside the Skill Master (not its own top-level nav entry — it's
    // filtered out of the sidebar in MasterDataPage).
    key: "domains",
    label: "Domains",
    singular: "domain",
    endpoint: "/domains/",
    pk: "domain_id",
    dedupeGroups: [["domain_name"]],
    similarField: "domain_name",
    columns: [{ key: "domain_name", header: "Domain" }],
    fields: [
      { name: "domain_name", label: "Domain name", type: "text", required: true, kind: "label", casing: "title", maxLength: 60, placeholder: "e.g. Data & Analytics" },
    ],
  },
  {
    key: "locations",
    label: "Locations",
    singular: "location",
    endpoint: "/locations/",
    pk: "location_id",
    dedupeGroups: [["city", "state", "country"]],
    similarField: "city",
    columns: [
      { key: "city", header: "City" },
      { key: "state", header: "State" },
      { key: "country", header: "Country" },
    ],
    fields: [
      { name: "city", label: "City", type: "text", required: true, kind: "place", casing: "title_strict", maxLength: 60 },
      { name: "state", label: "State / Union Territory", type: "state", required: true },
      { name: "country", label: "Country", type: "country", required: true },
    ],
  },
  {
    key: "sources",
    label: "Sources",
    singular: "source",
    endpoint: "/sources/",
    pk: "source_id",
    dedupeGroups: [["source_name"]],
    similarField: "source_name",
    columns: [
      { key: "source_name", header: "Source" },
      { key: "source_type", header: "Type" },
    ],
    fields: [
      { name: "source_name", label: "Source name", type: "text", required: true, kind: "label", casing: "title", maxLength: 60 },
      { name: "source_type", label: "Type", type: "text", kind: "label", casing: "title", maxLength: 40, placeholder: "e.g. Job Portal" },
    ],
  },
  {
    key: "notice-periods",
    label: "Notice Periods",
    singular: "notice period",
    endpoint: "/notice-periods/",
    pk: "np_id",
    dedupeGroups: [["np_name"]],
    similarField: "np_name",
    columns: [{ key: "np_name", header: "Notice period" }],
    fields: [{ name: "np_name", label: "Notice period", type: "text", required: true, kind: "label", casing: "title", maxLength: 30, placeholder: "e.g. 30 Days" }],
  },
  {
    key: "work-modes",
    label: "Work Modes",
    singular: "work mode",
    endpoint: "/work-modes/",
    autoCode: { field: "work_mode_code", source: "work_mode_name" },
    pk: "work_mode_id",
    dedupeGroups: [["work_mode_code"], ["work_mode_name"]],
    similarField: "work_mode_name",
    columns: [
      { key: "work_mode_code", header: "Code" },
      { key: "work_mode_name", header: "Name" },
    ],
    fields: [
      { name: "work_mode_code", label: "Code", type: "text", required: true, kind: "code", casing: "upper", maxLength: 10, placeholder: "WFO / WFH / HYB" },
      { name: "work_mode_name", label: "Name", type: "text", required: true, kind: "alphaamp", casing: "title", maxLength: 30 },
    ],
  },
  {
    key: "priorities",
    label: "Priorities",
    singular: "priority",
    endpoint: "/priorities/",
    pk: "priority_id",
    dedupeGroups: [["priority_name"]],
    similarField: "priority_name",
    columns: [
      { key: "priority_name", header: "Priority" },
      { key: "description", header: "Description" },
    ],
    fields: [
      { name: "priority_name", label: "Priority", type: "text", required: true, kind: "alpha", casing: "title", maxLength: 30 },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "screening-modes",
    label: "Screening Modes",
    singular: "screening mode",
    endpoint: "/screening-modes/",
    autoCode: { field: "mode_code", source: "mode_name" },
    pk: "screening_mode_id",
    dedupeGroups: [["mode_name"], ["mode_code"]],
    similarField: "mode_name",
    columns: [
      { key: "mode_name", header: "Mode" },
      { key: "mode_code", header: "Code" },
    ],
    fields: [
      { name: "mode_name", label: "Mode", type: "text", required: true, kind: "label", casing: "title", maxLength: 40, placeholder: "Telephonic / Video" },
      { name: "mode_code", label: "Code", type: "text", kind: "code", casing: "upper", maxLength: 20 },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "rejection-reasons",
    label: "Rejection Reasons",
    singular: "rejection reason",
    endpoint: "/rejection-reasons/",
    autoCode: { field: "reason_code", source: "reason_name" },
    pk: "reason_id",
    dedupeGroups: [["reason_name"], ["reason_code"]],
    similarField: "reason_name",
    columns: [
      { key: "reason_name", header: "Reason" },
      { key: "reason_code", header: "Code" },
    ],
    fields: [
      { name: "reason_name", label: "Reason", type: "text", required: true, kind: "label", casing: "title", maxLength: 80 },
      { name: "reason_code", label: "Code", type: "text", kind: "code", casing: "upper", maxLength: 30 },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "email-templates",
    label: "Email Templates",
    singular: "email template",
    endpoint: "/email-templates/",
    pk: "template_id",
    dedupeGroups: [["template_code"]],
    similarField: "name",
    columns: [
      { key: "name", header: "Name" },
      { key: "template_code", header: "Code" },
      { key: "subject", header: "Subject" },
    ],
    fields: [
      { name: "template_code", label: "Code", type: "text", required: true, kind: "code", casing: "upper", maxLength: 40, placeholder: "e.g. JD_EMAIL" },
      { name: "name", label: "Name", type: "text", required: true, kind: "label", casing: "title", maxLength: 80 },
      { name: "subject", label: "Subject", type: "text", required: true, maxLength: 255 },
      {
        name: "body",
        label: "Body",
        type: "textarea",
        required: true,
        rows: 12,
        hint: "Placeholders: {candidate_name} {role} {client} {location} {exp} {ctc} {notice} {skills} {sender}",
      },
    ],
  },
  {
    key: "req-types",
    label: "Requirement Types",
    singular: "requirement type",
    endpoint: "/req-types/",
    autoCode: { field: "req_type_code", source: "req_type_name" },
    pk: "req_type_id",
    dedupeGroups: [["req_type_code"], ["req_type_name"]],
    similarField: "req_type_name",
    columns: [
      { key: "req_type_code", header: "Code" },
      { key: "req_type_name", header: "Name" },
    ],
    fields: [
      { name: "req_type_code", label: "Code", type: "text", required: true, kind: "code", casing: "upper", maxLength: 10, placeholder: "FTE / TPR" },
      { name: "req_type_name", label: "Name", type: "text", required: true, kind: "alphaamp", casing: "title", maxLength: 60 },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "candidate-status",
    label: "Candidate Status",
    singular: "candidate status",
    endpoint: "/candidate-status/",
    autoCode: { field: "status_code", source: "status_name" },
    pk: "candidate_status_id",
    dedupeGroups: [["status_name"], ["status_code"]],
    similarField: "status_name",
    columns: [
      { key: "status_name", header: "Status" },
      { key: "status_code", header: "Code" },
    ],
    fields: [
      { name: "status_name", label: "Status", type: "text", required: true, kind: "label", casing: "title", maxLength: 60 },
      { name: "status_code", label: "Code", type: "text", kind: "code", casing: "upper", maxLength: 30, placeholder: "e.g. SAVED" },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "application-status",
    label: "Application Status",
    singular: "application status",
    endpoint: "/application-status/",
    autoCode: { field: "status_code", source: "status_name" },
    pk: "application_status_id",
    dedupeGroups: [["status_name"], ["status_code"]],
    similarField: "status_name",
    columns: [
      { key: "status_name", header: "Status" },
      { key: "status_code", header: "Code" },
    ],
    fields: [
      { name: "status_name", label: "Status", type: "text", required: true, kind: "label", casing: "title", maxLength: 60 },
      { name: "status_code", label: "Code", type: "text", kind: "code", casing: "upper", maxLength: 30, placeholder: "e.g. SHORTLISTED" },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "position-status",
    label: "Position Status",
    singular: "position status",
    endpoint: "/position-status/",
    autoCode: { field: "status_code", source: "status_name" },
    pk: "position_status_id",
    dedupeGroups: [["status_name"], ["status_code"]],
    similarField: "status_name",
    columns: [
      { key: "status_name", header: "Status" },
      { key: "status_code", header: "Code" },
    ],
    fields: [
      { name: "status_name", label: "Status", type: "text", required: true, kind: "label", casing: "title", maxLength: 60 },
      { name: "status_code", label: "Code", type: "text", kind: "code", casing: "upper", maxLength: 30, placeholder: "e.g. OPEN" },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "req-status",
    label: "Requirement Status",
    singular: "requirement status",
    endpoint: "/req-status/",
    autoCode: { field: "status_code", source: "status_name" },
    pk: "status_id",
    dedupeGroups: [["status_name"], ["status_code"]],
    similarField: "status_name",
    columns: [
      { key: "status_name", header: "Status" },
      { key: "status_code", header: "Code" },
    ],
    fields: [
      { name: "status_name", label: "Status", type: "text", required: true, kind: "alphaamp", casing: "title", maxLength: 50 },
      { name: "status_code", label: "Code", type: "text", kind: "code", casing: "upper", maxLength: 20, placeholder: "e.g. OPEN" },
      { name: "description", label: "Description", type: "text", maxLength: 200 },
    ],
  },
  {
    key: "clients",
    label: "Clients",
    singular: "client",
    endpoint: "/clients/",
    autoCode: { field: "client_code", source: "client_name" },
    pk: "client_id",
    dedupeGroups: [["client_code"], ["client_name"]],
    similarField: "client_name",
    columns: [
      { key: "client_code", header: "Code" },
      { key: "client_name", header: "Client" },
      { key: "industry", header: "Industry" },
    ],
    fields: [
      { name: "client_code", label: "Client code", type: "text", required: true, kind: "code", casing: "upper", maxLength: 50, placeholder: "e.g. TCS" },
      { name: "client_name", label: "Client name", type: "text", required: true, kind: "label", casing: "title", maxLength: 120 },
      { name: "industry", label: "Industry", type: "text", kind: "label", casing: "title", maxLength: 60 },
    ],
  },
  {
    key: "client-managers",
    label: "Client Managers",
    singular: "client manager",
    endpoint: "/client-managers/",
    pk: "client_mgr_id",
    dedupeGroups: [["client", "email"]],
    similarField: "manager_name",
    columns: [
      { key: "manager_name", header: "Manager" },
      { key: "client_name", header: "Client" },
      { key: "email", header: "Email" },
      { key: "designation", header: "Designation" },
    ],
    fields: [
      {
        name: "client",
        label: "Client",
        type: "select",
        required: true,
        optionsEndpoint: "/clients/",
        optionValue: "client_id",
        optionLabel: "client_name",
      },
      { name: "manager_name", label: "Manager name", type: "text", required: true, kind: "person", casing: "title", maxLength: 100 },
      { name: "email", label: "Email", type: "text", required: true, kind: "email", maxLength: 150 },
      { name: "designation", label: "Designation", type: "text", kind: "label", casing: "title", maxLength: 80 },
      { name: "mobile", label: "Mobile", type: "text", kind: "phone", maxLength: 15 },
      { name: "department", label: "Department", type: "text", kind: "label", casing: "title", maxLength: 60 },
    ],
  },
];
