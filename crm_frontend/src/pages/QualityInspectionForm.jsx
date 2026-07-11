import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";

function QualityInspectionForm() {
  const role = localStorage.getItem("role") || "Staff";
  const navigate = useNavigate();
  const [form, setForm] = useState({ inspection_point: "", product: "", overall_notes: "" });
  const [error, setError] = useState("");

  /**
   * Resolve inspection point text → integer ID.
   * Accepts numeric ID or name/code search against /quality/inspection-points.
   */
  const resolveInspectionPointId = async (text) => {
    const trimmed = text.trim();
    if (!trimmed) throw new Error("Inspection point is required.");
    if (/^\d+$/.test(trimmed)) return Number(trimmed);
    const points = await apiFetch("/quality/inspection-points");
    const match = points.find(
      (p) =>
        p.name.toLowerCase() === trimmed.toLowerCase() ||
        p.code.toLowerCase() === trimmed.toLowerCase()
    );
    if (!match) {
      const partial = points.find(
        (p) =>
          p.name.toLowerCase().includes(trimmed.toLowerCase()) ||
          p.code.toLowerCase().includes(trimmed.toLowerCase())
      );
      if (!partial)
        throw new Error(
          `Inspection point not found: "${trimmed}". Enter an exact name, code, or numeric ID.`
        );
      return partial.id;
    }
    return match.id;
  };

  /**
   * Resolve product text → integer ID, or null if blank.
   */
  const resolveProductId = async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return null;
    if (/^\d+$/.test(trimmed)) return Number(trimmed);
    const data = await apiFetch(`/products?search=${encodeURIComponent(trimmed)}&limit=20`);
    const products = data.items || (Array.isArray(data) ? data : []);
    const match = products.find(
      (p) => p.name.toLowerCase() === trimmed.toLowerCase()
    );
    if (!match) {
      if (products.length === 1) return products[0].id;
      throw new Error(
        `Product not found: "${trimmed}". Enter an exact name or numeric ID.`
      );
    }
    return match.id;
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const inspectionPointId = await resolveInspectionPointId(form.inspection_point);
      const productId = await resolveProductId(form.product);

      const body = {
        inspection_point_id: inspectionPointId,
        product_id: productId,
        reference_type: "manual",
        overall_notes: form.overall_notes || null,
      };
      const insp = await apiFetch("/quality/inspections", {
        method: "POST",
        body: JSON.stringify(body),
      });
      navigate(`/quality/inspections/${insp.id}`);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="New inspection" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/quality/inspections" className="crm-muted">← Inspections</Link>
        {error && <p className="crm-error crm-mt">{error}</p>}
        <form className="crm-form crm-mt" onSubmit={submit}>
          <div className="crm-form-field">
            <label>Inspection point</label>
            <input
              required
              value={form.inspection_point}
              onChange={(e) => setForm((f) => ({ ...f, inspection_point: e.target.value }))}
              placeholder="Enter name, code, or numeric ID"
            />
          </div>
          <div className="crm-form-field">
            <label>Product (optional)</label>
            <input
              value={form.product}
              onChange={(e) => setForm((f) => ({ ...f, product: e.target.value }))}
              placeholder="Enter product name or numeric ID"
            />
          </div>
          <div className="crm-form-field">
            <label>Notes</label>
            <textarea
              rows={2}
              value={form.overall_notes}
              onChange={(e) => setForm((f) => ({ ...f, overall_notes: e.target.value }))}
            />
          </div>
          <button type="submit" className="crm-btn">Create inspection</button>
        </form>
      </div>
    </DashboardLayout>
  );
}

export default QualityInspectionForm;
