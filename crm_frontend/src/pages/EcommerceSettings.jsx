import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { loadSettings, saveSettings, SettingsStatusMessages } from "../utils/settingsPage";

function EcommerceSettings() {
  const role = localStorage.getItem("role") || "Staff";
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings("/ecommerce/settings", setForm, setError);
  }, []);

  const save = (e) => {
    e.preventDefault();
    saveSettings("/ecommerce/settings", form, { setForm, setError, setSaved });
  };

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  return (
    <DashboardLayout title="Store settings" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/ecommerce" className="crm-muted">← Online Store</Link>
        <SettingsStatusMessages error={error} saved={saved} />
        {form && (
          <form className="crm-form crm-mt" onSubmit={save}>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.is_enabled} onChange={(e) => setField("is_enabled", e.target.checked)} /> Enable online store</label>
            </div>
            <div className="crm-form-field"><label>Store name</label><input value={form.store_name || ""} onChange={(e) => setField("store_name", e.target.value)} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.guest_checkout_allowed} onChange={(e) => setField("guest_checkout_allowed", e.target.checked)} /> Allow guest checkout</label>
            </div>
            <div className="crm-form-field"><label>Flat shipping rate (₹)</label><input type="number" value={form.flat_shipping_rate} onChange={(e) => setField("flat_shipping_rate", e.target.value)} /></div>
            <div className="crm-form-field"><label>Free shipping above (₹)</label><input type="number" value={form.free_shipping_above || ""} onChange={(e) => setField("free_shipping_above", e.target.value || null)} /></div>
            <div className="crm-form-field"><label>Order number prefix</label><input value={form.order_number_prefix} onChange={(e) => setField("order_number_prefix", e.target.value)} /></div>
            <div className="crm-form-field"><label>Return window (days)</label><input type="number" value={form.return_window_days} onChange={(e) => setField("return_window_days", Number(e.target.value))} /></div>
            <div className="crm-form-field">
              <label><input type="checkbox" checked={form.auto_create_sales_order} onChange={(e) => setField("auto_create_sales_order", e.target.checked)} /> Auto-create sales order</label>
            </div>
            <div className="crm-form-field"><label>Bank / UPI details</label><textarea rows={3} value={form.bank_details || ""} onChange={(e) => setField("bank_details", e.target.value)} /></div>
            {form.public_shop_url && <p className="crm-muted">Public shop: <a href={form.public_shop_url} target="_blank" rel="noreferrer">{form.public_shop_url}</a></p>}
            <button type="submit" className="crm-btn">Save settings</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

export default EcommerceSettings;
