import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { formatCurrency, RATE_BASIS_LABELS } from "../utils/rental";

function RentalContractForm() {
  const role = localStorage.getItem("role") || "Staff";
  const navigate = useNavigate();
  const [contacts, setContacts] = useState([]);
  const [assets, setAssets] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    contact_id: "",
    rate_basis: "daily",
    rental_start: "",
    rental_end: "",
    delivery_address: "",
    notes: "",
    lines: [{ rental_asset_id: "", quantity: 1 }],
  });

  useEffect(() => {
    Promise.all([
      apiFetch("/contacts?limit=100"),
      apiFetch("/rental/assets?status=active"),
    ])
      .then(([cData, aData]) => {
        setContacts(cData.items || []);
        setAssets(Array.isArray(aData) ? aData : []);
      })
      .catch((err) => setError(err.message));
  }, []);

  const updateLine = (idx, field, value) => {
    setForm((f) => {
      const lines = [...f.lines];
      lines[idx] = { ...lines[idx], [field]: value };
      return { ...f, lines };
    });
  };

  const addLine = () => setForm((f) => ({ ...f, lines: [...f.lines, { rental_asset_id: "", quantity: 1 }] }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const body = {
        contact_id: Number(form.contact_id),
        rate_basis: form.rate_basis,
        rental_start: new Date(form.rental_start).toISOString(),
        rental_end: new Date(form.rental_end).toISOString(),
        delivery_address: form.delivery_address || null,
        notes: form.notes || null,
        lines: form.lines
          .filter((l) => l.rental_asset_id)
          .map((l) => ({ rental_asset_id: Number(l.rental_asset_id), quantity: Number(l.quantity) || 1 })),
      };
      const data = await apiFetch("/rental/contracts", { method: "POST", body: JSON.stringify(body) });
      navigate(`/rental/contracts/${data.id}`);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="New rental contract" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/rental/contracts" className="crm-muted">← Contracts</Link>
        {error && <p className="crm-error crm-mt">{error}</p>}
        <form className="crm-form crm-mt" onSubmit={submit}>
          <div className="crm-form-field">
            <label>Contact</label>
            <select required value={form.contact_id} onChange={(e) => setForm({ ...form, contact_id: e.target.value })}>
              <option value="">Select contact</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="crm-form-row">
            <div className="crm-form-field">
              <label>Rate basis</label>
              <select value={form.rate_basis} onChange={(e) => setForm({ ...form, rate_basis: e.target.value })}>
                {Object.entries(RATE_BASIS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="crm-form-field">
              <label>Rental start</label>
              <input type="datetime-local" required value={form.rental_start} onChange={(e) => setForm({ ...form, rental_start: e.target.value })} />
            </div>
            <div className="crm-form-field">
              <label>Rental end</label>
              <input type="datetime-local" required value={form.rental_end} onChange={(e) => setForm({ ...form, rental_end: e.target.value })} />
            </div>
          </div>
          <div className="crm-form-field">
            <label>Delivery address</label>
            <textarea value={form.delivery_address} onChange={(e) => setForm({ ...form, delivery_address: e.target.value })} />
          </div>
          <h4>Lines</h4>
          {form.lines.map((line, idx) => (
            <div key={idx} className="crm-form-row crm-mt">
              <select required value={line.rental_asset_id} onChange={(e) => updateLine(idx, "rental_asset_id", e.target.value)}>
                <option value="">Select asset</option>
                {assets.map((a) => (
                  <option key={a.id} value={a.id}>{a.asset_code} — {a.name} ({formatCurrency(a.rate_daily)}/day)</option>
                ))}
              </select>
              <input type="number" min="1" value={line.quantity} onChange={(e) => updateLine(idx, "quantity", e.target.value)} />
            </div>
          ))}
          <button type="button" className="crm-btn crm-btn-sm crm-btn-outline crm-mt" onClick={addLine}>Add line</button>
          <div className="crm-form-field crm-mt">
            <label>Notes</label>
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          <button type="submit" className="crm-btn crm-mt">Create draft contract</button>
        </form>
      </div>
    </DashboardLayout>
  );
}

export default RentalContractForm;
