import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { emptyProjectForm } from "../utils/projects";

// Valid enum values accepted by the backend
const VALID_TYPES = ["client", "internal"];
const VALID_STATUSES = ["draft", "active", "on_hold", "completed", "cancelled"];
const VALID_PRIORITIES = ["low", "normal", "high"];

function ProjectForm() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const role = localStorage.getItem("role") || "Staff";

  // Text fields shown to the user
  const [form, setForm] = useState({
    ...emptyProjectForm(),
    contact_id: searchParams.get("contact_id") || "",
    deal_id: searchParams.get("deal_id") || "",
    sales_order_id: searchParams.get("sales_order_id") || "",
  });

  // Display names for manager and contact (shown in text inputs when editing)
  const [managerText, setManagerText] = useState("");
  const [contactText, setContactText] = useState("");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(isEdit);

  useEffect(() => {
    if (isEdit) {
      apiFetch(`/projects/${id}`)
        .then((p) => {
          setForm({
            name: p.name,
            description: p.description || "",
            project_type: p.project_type,
            status: p.status,
            priority: p.priority,
            contact_id: p.contact_id ? String(p.contact_id) : "",
            deal_id: p.deal_id ? String(p.deal_id) : "",
            sales_order_id: p.sales_order_id ? String(p.sales_order_id) : "",
            project_manager_id: String(p.project_manager_id),
            start_date: p.start_date ? p.start_date.slice(0, 10) : "",
            deadline: p.deadline ? p.deadline.slice(0, 10) : "",
          });
          // Pre-fill display names from the response
          setManagerText(p.project_manager_name || String(p.project_manager_id));
          setContactText(p.contact_name || (p.contact_id ? String(p.contact_id) : ""));
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [id, isEdit]);

  /**
   * Resolve a free-text name to an integer user ID.
   * Tries exact numeric match first, then name search against /projects/assignees.
   */
  const resolveManagerId = async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return null;
    // If user typed a plain number, use it directly
    if (/^\d+$/.test(trimmed)) return Number(trimmed);
    // Otherwise search assignees by name
    const assignees = await apiFetch("/projects/assignees");
    const match = assignees.find(
      (u) => u.name.toLowerCase() === trimmed.toLowerCase()
    );
    if (!match) {
      // Try partial match
      const partial = assignees.find((u) =>
        u.name.toLowerCase().includes(trimmed.toLowerCase())
      );
      if (!partial) throw new Error(`Project manager not found: "${trimmed}". Please enter an exact name or numeric ID.`);
      return partial.id;
    }
    return match.id;
  };

  /**
   * Resolve a free-text contact name/number to an integer contact ID.
   * Returns null if blank.
   */
  const resolveContactId = async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return null;
    if (/^\d+$/.test(trimmed)) return Number(trimmed);
    const data = await apiFetch(`/contacts?search=${encodeURIComponent(trimmed)}&limit=20`);
    const contacts = data.items || [];
    const match = contacts.find(
      (c) => c.name.toLowerCase() === trimmed.toLowerCase()
    );
    if (!match) {
      if (contacts.length === 1) return contacts[0].id;
      throw new Error(`Contact not found: "${trimmed}". Please enter an exact name or numeric ID.`);
    }
    return match.id;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Validate enum fields client-side for a clear message
    const typeLower = form.project_type.trim().toLowerCase();
    if (!VALID_TYPES.includes(typeLower)) {
      setError(`Type must be one of: ${VALID_TYPES.join(", ")}`);
      return;
    }
    const statusLower = form.status.trim().toLowerCase();
    if (!VALID_STATUSES.includes(statusLower)) {
      setError(`Status must be one of: ${VALID_STATUSES.join(", ")}`);
      return;
    }
    const priorityLower = form.priority.trim().toLowerCase();
    if (!VALID_PRIORITIES.includes(priorityLower)) {
      setError(`Priority must be one of: ${VALID_PRIORITIES.join(", ")}`);
      return;
    }
    if (!managerText.trim()) {
      setError("Project manager is required");
      return;
    }

    try {
      // Resolve name→ID for FK fields
      const managerId = await resolveManagerId(managerText);
      const contactId = await resolveContactId(contactText);

      const payload = {
        name: form.name.trim(),
        description: form.description || null,
        project_type: typeLower,
        status: statusLower,
        priority: priorityLower,
        contact_id: contactId,
        deal_id: form.deal_id ? Number(form.deal_id) : null,
        sales_order_id: form.sales_order_id ? Number(form.sales_order_id) : null,
        project_manager_id: managerId,
        start_date: form.start_date
          ? new Date(`${form.start_date}T00:00:00`).toISOString()
          : null,
        deadline: form.deadline
          ? new Date(`${form.deadline}T23:59:59`).toISOString()
          : null,
      };

      if (isEdit) {
        await apiFetch(`/projects/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        navigate(`/projects/${id}`);
      } else {
        const created = await apiFetch("/projects", { method: "POST", body: JSON.stringify(payload) });
        navigate(`/projects/${created.id}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <DashboardLayout title={isEdit ? "Edit project" : "New project"} roleLabel={role}>
        <div className="crm-panel"><p>Loading…</p></div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout title={isEdit ? "Edit project" : "New project"} roleLabel={role}>
      <div className="crm-panel">
        <Link to={isEdit ? `/projects/${id}` : "/projects"} className="crm-link crm-link-left">← Back</Link>
        {error && <p className="crm-error crm-mt">{error}</p>}
        <form onSubmit={handleSubmit} className="crm-form crm-mt">
          <div className="crm-form-grid">
            <label>
              Project name *
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </label>
            <label>
              Type
              <input
                value={form.project_type}
                onChange={(e) => setForm({ ...form, project_type: e.target.value })}
                placeholder="client or internal"
              />
            </label>
            <label>
              Status
              <input
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                placeholder="draft, active, on_hold…"
              />
            </label>
            <label>
              Priority
              <input
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
                placeholder="low, normal, or high"
              />
            </label>
            <label>
              Project manager *
              <input
                value={managerText}
                onChange={(e) => setManagerText(e.target.value)}
                required
                placeholder="Enter name or numeric ID"
              />
            </label>
            <label>
              Client contact
              <input
                value={contactText}
                onChange={(e) => setContactText(e.target.value)}
                placeholder="Enter name or numeric ID"
              />
            </label>
            <label>
              Start date
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </label>
            <label>
              Deadline
              <input
                type="date"
                value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: e.target.value })}
              />
            </label>
            <label>
              Deal ID (optional)
              <input
                value={form.deal_id}
                onChange={(e) => setForm({ ...form, deal_id: e.target.value })}
                placeholder="Link to deal"
              />
            </label>
            <label>
              Sales order ID (optional)
              <input
                value={form.sales_order_id}
                onChange={(e) => setForm({ ...form, sales_order_id: e.target.value })}
                placeholder="Link to order"
              />
            </label>
          </div>
          <label className="crm-mt">
            Description
            <textarea
              rows={4}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
          <div className="crm-form-actions crm-mt">
            <button type="submit" className="crm-btn">
              {isEdit ? "Save changes" : "Create project"}
            </button>
          </div>
        </form>
      </div>
    </DashboardLayout>
  );
}

export default ProjectForm;
